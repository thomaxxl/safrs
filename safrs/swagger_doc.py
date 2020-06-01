"""
Functions for api documentation: these decorators generate the swagger schemas

This should evolve to a more declarative version in the future with templates
"""
import inspect
import datetime
import json
import flask
from http import HTTPStatus
import yaml
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY  # , MANYTOONE
from flask_restful_swagger_2 import Schema, swagger
from safrs.errors import ValidationError
from safrs.config import get_config, is_debug
import safrs


REST_DOC = "__rest_doc"  # swagger doc attribute name. If this attribute is set
# this means that the function is reachable through HTTP POST
HTTP_METHODS = "__http_method"
DOC_DELIMITER = "---"  # used as delimiter between the rest_doc swagger yaml spec
# and regular documentation
PAGEABLE = "pageable"  # denotes whether an api method is pageable
FILTERABLE = "filterable"

# additional responses added when in debug mode to make swagger-check succeed
debug_responses = {
    HTTPStatus.METHOD_NOT_ALLOWED.value: {"description": HTTPStatus.METHOD_NOT_ALLOWED.description},
    HTTPStatus.BAD_REQUEST.value: {"description": HTTPStatus.BAD_REQUEST.description},
    HTTPStatus.INTERNAL_SERVER_ERROR.value: {"description": HTTPStatus.INTERNAL_SERVER_ERROR.description},
}


# pylint: disable=redefined-builtin,line-too-long,protected-access,logging-format-interpolation
def parse_object_doc(object):
    """
        Parse the yaml description from the documented methods
    """
    api_doc = {}
    obj_doc = str(inspect.getdoc(object))
    raw_doc = obj_doc.split(DOC_DELIMITER)[0]
    yaml_doc = None

    try:
        yaml_doc = yaml.safe_load(raw_doc)
    except (SyntaxError, yaml.scanner.ScannerError) as exc:
        safrs.log.error("Failed to parse documentation {} ({})".format(raw_doc, exc))
        yaml_doc = {"description": raw_doc}
    except Exception:
        raise ValidationError("Failed to parse api doc")

    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)

    return api_doc


def jsonapi_rpc(http_methods, valid_jsonapi=True):
    """
        Decorator to expose functions in the REST API:
        When a method is decorated with jsonapi_rpc, this means
        it becomes available for use through HTTP POST (i.e. public)

        :param http_methods:
        :return: function
    """

    def _documented_api_method(method):
        """
            :param method:
            add metadata to the method:
                REST_DOC: swagger documentation
                HTTP_METHODS: the http methods (GET/POST/..) used to call this method
        """
        USE_API_METHODS = get_config("USE_API_METHODS")
        if USE_API_METHODS:
            try:
                api_doc = parse_object_doc(method)
            except yaml.scanner.ScannerError:
                safrs.log.error("Failed to parse documentation for %s", method)
            setattr(method, REST_DOC, api_doc)
            setattr(method, HTTP_METHODS, http_methods)
            setattr(method, "valid_jsonapi", valid_jsonapi)
        return method

    return _documented_api_method


def is_public(method):
    """
        :param method:
        :return: True or False, whether the method is to be exposed
    """

    return hasattr(method, REST_DOC)


def get_doc(method):
    """
        :param  method:
        :return: OAS documentation
    """

    return getattr(method, REST_DOC, None)


def get_http_methods(method):
    """
        :param method:
        :return: a list of http methods used to call this method
    """

    return getattr(method, HTTP_METHODS, ["POST"])


def SchemaClassFactory(name, properties):
    """
        Generate a Schema class, used to describe swagger schemas
        :param name: schema class name
        :param properties: class attributes
        :return: class
    """

    # generate a unique name to be used as a reference
    idx = Schema._reference_count.count(name)
    if idx:
        name = name + str(idx)
    # name = urllib.parse.quote(name)
    Schema._reference_count.append(name)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the properties variable is the one passed to the
            # ClassFactory call
            if key not in properties:
                raise ValidationError("Argument {} not valid for {}".format(key, self.__class__.__name__))
            setattr(self, key, value)

    new_schema_cls = type(name, (Schema,), {"__init__": __init__, "properties": properties})
    Schema._references[name] = new_schema_cls
    return new_schema_cls


# List to generate the swagger references / definitions unique name
Schema._reference_count = []
Schema._references = {}


def encode_schema(obj):
    """
        None aka "null" is invalid in swagger schema definition
        This breaks our samples :/
        We don't add the item to the schema if it's None
    """
    result = ""

    if obj is not None:
        try:
            result = json.loads(json.dumps(obj, cls=flask.current_app.json_encoder))
        except Exception as exc:
            safrs.log.warning("Json encoding failed for {}, type {} ({})".format(obj, type(obj), exc))
            result = str(obj)

    return result


# pylint: disable=redefined-builtin
def schema_from_object(name, object):
    """
        :param name:
        :param object:
        :return: swagger schema object
    """

    properties = {}

    if isinstance(object, str):
        properties = {"example": "", "type": "string"}

    elif isinstance(object, int):
        properties = {"example": 0, "type": "integer"}

    elif isinstance(object, (datetime.datetime, datetime.date, datetime.time)):
        properties = {"example": str(object), "type": "string"}

    elif isinstance(object, dict):
        for k, v in object.items():
            if isinstance(v, str):
                properties[k] = {"example": v, "type": "string"}
            elif isinstance(v, int):
                properties[k] = {"example": v, "type": "integer"}
            elif isinstance(v, (dict, list)):
                if isinstance(v, dict):
                    v = encode_schema(v)
                properties[k] = {"example": v, "type": "string"}
            elif v is None:
                # swagger doesn't allow null values
                properties[k] = {"example": "", "type": "string"}
            else:  # isinstance(object, datetime.datetime):
                properties = {"example": str(k), "type": "string"}
                safrs.log.warning("Invalid schema object type %s", type(object))
    else:
        raise ValidationError("Invalid schema object type {}".format(type(object)))

    properties = encode_schema(properties)
    schema = SchemaClassFactory(name, properties)
    return schema


def get_swagger_doc_arguments(cls, method_name, http_method):
    """
        :param cls: class containing the method to be exposed
        :param method_name: name of the method to be exposed
        :param http_method: HTTP method used to invoke
        :return: parameters, fields, description, method

        create a schema for all methods which can be called through the
        REST POST interface

        A method is called with following JSON payload:
        ```{
            "meta"   : {
                         "args" : {
                                    "parameter1" : "value1" ,
                                    "parameter2" : "value2" ,
                                  }
                       }
        }```

        The schema is created using the values from the documented_api_method decorator,
        returned by get_doc()

        We use "meta" to remain compliant with the jsonapi schema
    """

    parameters = []
    # for method_name, method in inspect.getmembers(cls, predicate=inspect.ismethod):
    for name, method in inspect.getmembers(cls):
        if name != method_name:
            continue

        fields = {}
        rest_doc = get_doc(method)
        description = rest_doc.get("description", "")
        if rest_doc:
            method_args = rest_doc.get("args", [])  # jsonapi_rpc "POST" method arguments
            parameters = rest_doc.get("parameters", [])  # query string parameters
            if method_args and isinstance(method_args, dict):
                if http_method == "post":
                    """
                        Post arguments, these require us to build a schema
                    """
                    model_name = "{}_{}".format(cls.__name__, method_name)
                    method_field = {"method": method_name, "args": method_args}
                    fields["meta"] = schema_from_object(model_name, method_field)
            if rest_doc.get(PAGEABLE):
                parameters += default_paging_parameters()
            if rest_doc.get(FILTERABLE):
                for column_name, column in cls._s_column_dict.items():
                    # Expose a column if it doesn't have the "expose" attribute
                    # Standard SQLA columns don't have this attibute
                    # but this may have been customized by a subclass
                    if getattr(column, "expose", True) and getattr(column, FILTERABLE, True):
                        description = getattr(column, "description", "{} attribute filter (csv)".format(column_name))
                        param = {
                            "default": "",
                            "type": "string",
                            "name": "filter[{}]".format(column_name),
                            "in": "query",
                            "format": "string",
                            "required": False,
                            "description": description,
                        }
                        parameters += param
        else:
            safrs.log.warning('No documentation for method "{}"'.format(method_name))
            # jsonapi_rpc method has no documentation, generate it w/ inspect
            f_args = inspect.getfullargspec(method).args
            f_defaults = inspect.getfullargspec(method).defaults or []
            if f_args[0] in ("cls", "self"):
                f_args = f_args[1:]
            args = dict(zip(f_args, f_defaults))
            model_name = "{}_{}".format(cls.__name__, method_name)
            # model = SchemaClassFactory(model_name, [])
            # arg_field = {"schema": model, "type": "string"} # tbd?
            method_field = {"method": method_name, "args": args}
            fields["meta"] = schema_from_object(model_name, method_field)

        for param in parameters:
            if param.get("in") is None:
                param["in"] = "query"
            if param.get("type") is None:
                param["type"] = "string"

        return parameters, fields, description, method


#
# Decorator is called when a swagger endpoint class is instantiated
# from API.expose_object eg.
#
def swagger_doc(cls, tags=None):
    """
    swagger_doc
    """

    def swagger_doc_gen(func, instance=False):
        """
            Decorator used to document SAFRSRestAPI HTTP methods exposed in the API
        """
        default_id = cls._s_sample_id()
        class_name = cls.__name__
        collection_name = cls._s_collection_name
        http_method = func.__name__.lower()
        parameters = [
            {
                "name": cls._s_object_id,
                "in": "path",
                "type": "string",
                "default": default_id,
                "required": True,
            },  # parameter id, e.g. UserId
            {
                "name": "Content-Type",  # parameter id, e.g. UserId
                "in": "header",
                "type": "string",
                "default": "application/vnd.api+json",
                "enum": ["application/vnd.api+json", "application/json"],
                "required": True,
            },
        ]
        if tags is None:
            doc_tags = [collection_name]
        else:
            doc_tags = tags

        doc = {"tags": doc_tags}

        responses = {}
        # adhere to open api
        # the model_name will hold the OAS "$ref" schema reference
        coll_model_name = "{}_{}_coll".format(class_name, http_method)  # collection model name
        inst_model_name = "{}_{}_inst".format(class_name, http_method)  # instance model name

        sample_dict = cls._s_sample_dict()

        # Samples with "id" are used for GET and PATCH
        coll_sample_data = schema_from_object(
            coll_model_name, {"data": [{"attributes": sample_dict, "type": cls._s_type, "id": cls._s_sample_id()}]}
        )

        inst_sample_data = schema_from_object(
            inst_model_name, {"data": {"attributes": sample_dict, "type": cls._s_type, "id": cls._s_sample_id()}}
        )

        cls.swagger_models["instance"] = inst_sample_data
        cls.swagger_models["collection"] = coll_sample_data

        if http_method == "get":
            doc["summary"] = "Retrieve a {} object".format(class_name)
            doc["collection_summary"] = "Retrieve a collection of {} objects".format(class_name)
            body, responses = cls._s_get_swagger_doc(http_method)
            responses[HTTPStatus.OK.value] = {"schema": coll_sample_data}

        elif http_method == "patch":
            post_model, responses = cls._s_get_swagger_doc(http_method)

            parameters.append(
                {
                    "name": "PATCH body",
                    "in": "body",
                    "description": "{} attributes".format(class_name),
                    "schema": inst_sample_data,
                    "required": True,
                }
            )
        elif http_method == "post":
            _, responses = cls._s_get_swagger_doc(http_method)
            doc["summary"] = "Create a {} object".format(class_name)

            # Create the default POST body schema
            sample_dict = cls._s_sample_dict()
            # The POST sample doesn't contain an "id"
            sample_data = schema_from_object(inst_model_name, {"data": {"attributes": sample_dict, "type": cls._s_type}})
            parameters.append(
                {
                    "name": "POST body",
                    "in": "body",
                    "description": "{} attributes".format(class_name),
                    "schema": sample_data,
                    "required": True,
                }
            )

        elif http_method == "delete":
            _, responses = cls._s_get_swagger_doc(http_method)
        else:
            # one of 'options', 'head', 'delete'
            safrs.log.debug('no additional documentation for "{}" '.format(func))

        if is_debug():
            responses.update(debug_responses)

        doc["parameters"] = parameters
        doc["responses"] = responses
        doc["produces"] = ["application/vnd.api+json"]

        method_doc = parse_object_doc(func)
        safrs.dict_merge(doc, method_doc)
        apply_fstring(doc, locals())
        return swagger.doc(doc)(func)

    return swagger_doc_gen


def swagger_relationship_doc(cls, tags=None):
    """
    swagger_relationship_doc
    """

    def swagger_doc_gen(func):
        """
            Decorator used to document relationship methods exposed in the API
        """

        parent_class = cls.relationship.parent.class_
        child_class = cls.relationship.mapper.class_
        class_name = cls.__name__
        http_method = func.__name__.lower()
        #######################################################################
        # Following will only happen when exposing an exisiting DB
        #
        if not getattr(parent_class, "object_id", None):
            parent_class._s_object_id = parent_class.__name__ + "Id"
        if not getattr(child_class, "object_id", None):
            child_class._s_object_id = child_class.__name__ + "Id"
        if not getattr(parent_class, "sample_id", None):
            setattr(parent_class, "sample_id", lambda: "")
        if not getattr(child_class, "sample_id", None):
            setattr(child_class, "sample_id", lambda: "")
        if not getattr(child_class, "get_swagger_doc", None):
            setattr(child_class, "get_swagger_doc", lambda x: (None, {}))
        #
        #######################################################################

        parameters = [
            {
                "name": parent_class._s_object_id,
                "in": "path",
                "type": "string",
                "default": parent_class._s_sample_id(),
                "description": "{} item".format(parent_class.__name__),
                "required": True,
            },
            {
                "name": child_class._s_object_id,
                "in": "path",
                "type": "string",
                "default": child_class._s_sample_id(),
                "description": "{} item".format(class_name),
                "required": True,
            },
        ]

        if tags is None:
            doc_tags = [cls._s_collection_name]
        else:
            doc_tags = tags

        doc = {"tags": doc_tags}
        doc.update(parse_object_doc(func))

        responses = {}
        if http_method == "get":
            _, responses = cls._s_get_swagger_doc(http_method)
        elif http_method in ("post", "patch"):
            _, responses = cls._s_get_swagger_doc(http_method)
            child_sample_id = child_class._s_sample_id()

            _, responses = child_class._s_get_swagger_doc("patch")
            data = {"type": child_class._s_type, "id": child_sample_id}

            if cls.relationship.direction in (ONETOMANY, MANYTOMANY):
                data = [data]
            rel_post_schema = schema_from_object("{}_Relationship".format(class_name), {"data": data})
            parameters.append(
                {
                    "name": "{} body".format(class_name),
                    "in": "body",
                    "description": "{} POST model".format(class_name),
                    "schema": rel_post_schema,
                    "required": True,
                }
            )

        elif http_method == "delete":
            child_sample_id = child_class._s_sample_id()

            _, responses = child_class._s_get_swagger_doc("patch")
            data = {"type": child_class._s_type, "id": child_sample_id}

            if cls.relationship.direction in (ONETOMANY, MANYTOMANY):
                data = [data]
            rel_del_schema = schema_from_object("{}_Relationship".format(class_name), {"data": data})
            parameters.append(
                {
                    "name": "{} body".format(class_name),
                    "in": "body",
                    "description": "{} POST model".format(class_name),
                    "schema": rel_del_schema,
                    "required": True,
                }
            )

        else:
            # one of 'options', 'head', 'patch'
            safrs.log.info('no documentation for "{}" '.format(http_method))

        doc["parameters"] = parameters
        if doc.get("responses"):
            responses.update({str(val): desc for val, desc in doc["responses"].items()})

        if is_debug():
            responses.update(debug_responses)

        doc["responses"] = responses

        direction = "to-many" if cls.relationship.direction in (ONETOMANY, MANYTOMANY) else "to-one"
        parent_name = parent_class.__name__  # to be used by f-string
        child_name = child_class.__name__  # to be used by f-string
        apply_fstring(doc, locals())
        return swagger.doc(doc)(func)

    return swagger_doc_gen


def swagger_method_doc(cls, method_name, tags=None):
    """
        Generate decorator used to document SAFRSJSONRPCAPI instances
    """

    def swagger_doc_gen(func):
        """
            decorator
        """
        method = getattr(cls, method_name, None)
        method_doc = parse_object_doc(method)
        class_name = cls.__name__
        if tags is None:
            doc_tags = [cls._s_collection_name]
        else:
            doc_tags = tags

        responses = method_doc.get("responses", {HTTPStatus.OK.value: {"description": HTTPStatus.OK.description}})
        if is_debug():
            responses.update(debug_responses)

        summary = method_doc.get("summary", "Invoke {}.{}".format(class_name, method_name))
        description = method_doc.get("description", summary)

        doc = {"tags": doc_tags, "description": description, "summary": summary, "responses": responses}

        model_name = "{}_{}_{}".format("Invoke ", class_name, method_name)
        param_model = SchemaClassFactory(model_name, {})
        parameters, fields, description, method = get_swagger_doc_arguments(cls, method_name, http_method=func.__name__)

        if func.__name__ == "get":
            if not parameters:
                parameters = [
                    {
                        "name": "varargs",
                        "in": "query",
                        "description": "{} arguments".format(method_name),
                        "required": False,
                        "type": "string",
                    }
                ]
        else:
            # Retrieve the swagger schemas for the jsonapi_rpc methods from the docstring
            parameters, fields, description, method = get_swagger_doc_arguments(cls, method_name, http_method=func.__name__)
            model_name = "{}_{}_{}".format(func.__name__, cls.__name__, method_name)
            param_model = SchemaClassFactory(model_name, fields)

            parameters.append({"name": model_name, "in": "body", "description": description, "schema": param_model, "required": True})

        # URL Path Parameter
        default_id = cls._s_sample_id()
        parameters.append(
            {"name": cls._s_object_id, "in": "path", "type": "string", "default": default_id, "required": True}
        )  # parameter id, e.g. UserId
        doc["parameters"] = parameters
        doc["produces"] = ["application/vnd.api+json"]

        apply_fstring(doc, locals())
        return swagger.doc(doc)(func)

    return swagger_doc_gen


def default_paging_parameters():
    """
        default_paging_parameters
    """

    parameters = []
    param = {
        "default": 0,  # The 0 isn't rendered though
        "type": "integer",
        "name": "page[offset]",
        "in": "query",
        "format": "int64",
        "required": False,
        "description": "Page offset",
    }
    parameters.append(param)

    param = {
        "default": 10,
        "type": "integer",
        "name": "page[limit]",
        "in": "query",
        "format": "int64",
        "required": False,
        "description": "Max number of items",
    }
    parameters.append(param)
    return parameters


def apply_fstring(swagger_obj, vars, k=None):
    """
        Format the f-strings in the swagger object
    """
    if isinstance(swagger_obj, str):
        return swagger_obj.format(**vars)
    elif isinstance(swagger_obj, list):
        for i in swagger_obj:
            apply_fstring(i, vars)
    elif isinstance(swagger_obj, dict):
        for k, v in swagger_obj.copy().items():
            new_v = apply_fstring(v, vars)
            if isinstance(k, int):
                # used to convert integer codes (from the responses)
                del swagger_obj[k]
                k = str(k)
            swagger_obj[k] = new_v

    return swagger_obj
