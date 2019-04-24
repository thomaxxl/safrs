"""
Functions for api documentation: these decorators generate the swagger schemas
"""
import inspect
import logging
import datetime
import yaml
import decimal
from flask_restful_swagger_2 import Schema, swagger
from safrs.errors import ValidationError
from safrs.config import get_config
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY  # , MANYTOONE
import safrs

REST_DOC = "__rest_doc"  # swagger doc attribute name. If this attribute is set
# this means that the function is reachable through HTTP POST
HTTP_METHODS = "__http_method"
DOC_DELIMITER = "---"  # used as delimiter between the rest_doc swagger yaml spec
# and regular documentation
PAGEABLE = "pageable"  # denotes whether an api method is pageable
FILTERABLE = "filterable"

# pylint: disable=redefined-builtin,line-too-long
def parse_object_doc(object):
    """
        Parse the yaml description from the documented methods
    """
    api_doc = {}
    obj_doc = str(inspect.getdoc(object))
    raw_doc = obj_doc.split(DOC_DELIMITER)[0]
    yaml_doc = None

    try:
        yaml_doc = yaml.load(raw_doc)
    except (SyntaxError, yaml.scanner.ScannerError) as exc:
        safrs.LOGGER.error("Failed to parse documentation {} ({})".format(raw_doc, exc))
        yaml_doc = {"description": raw_doc}

    except Exception as exc:

        raise ValidationError("Failed to parse api doc")

    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)

    return api_doc


def documented_api_method(method):
    """
        Decorator to expose functions in the REST API:
        When a method is decorated with documented_api_method, this means
        it becomes available for use through HTTP POST (i.e. public)
    """
    USE_API_METHODS = get_config("USE_API_METHODS")
    if USE_API_METHODS:
        try:
            api_doc = parse_object_doc(method)
        except yaml.scanner.ScannerError:
            safrs.LOGGER.error("Failed to parse documentation for %s", method)
        setattr(method, REST_DOC, api_doc)
    return method


def jsonapi_rpc(http_methods):
    """
        :param http_methods:
    """

    def _documented_api_method(method):
        """
            Decorator to expose functions in the REST API:
            When a method is decorated with documented_api_method, this means
            it becomes available for use through HTTP POST (i.e. public)
        """
        USE_API_METHODS = get_config("USE_API_METHODS")
        if USE_API_METHODS:
            try:
                api_doc = parse_object_doc(method)
            except yaml.scanner.ScannerError:
                safrs.LOGGER.error("Failed to parse documentation for %s", method)
            setattr(method, REST_DOC, api_doc)
            setattr(method, HTTP_METHODS, http_methods)
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
    get_http_methods
    """
    return getattr(method, HTTP_METHODS, ["POST"])


def SchemaClassFactory(name, properties):
    """
        Generate a Schema class, used to describe swagger schemas
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the properties variable is the one passed to the
            # ClassFactory call
            if key not in properties:
                raise ValidationError(
                    "Argument {} not valid for {}".format(
                        (key, self.__class__.__name__)
                    )
                )
            setattr(self, key, value)

    newclass = type(name, (Schema,), {"__init__": __init__, "properties": properties})

    return newclass


_references = []


def encode_schema(obj):
    """
        None aka "null" is invalid in swagger schema definition
        This breaks our samples :/
        We don't add the item to the schema if it's None
    """
    if obj is None:
        return None
    if isinstance(obj, (datetime.datetime, datetime.date, decimal.Decimal, bytes)):
        return str(obj)
    if isinstance(obj, dict):
        result = {}
        for key, val in obj.items():
            val = encode_schema(val)
            if val is None:
                result[key] = ""
            else:
                result[key] = val
        return result
    if isinstance(obj, (list, set)):
        result = []
        for i in obj:
            encoded = encode_schema(i)
            if not encoded is None:
                result.append(encoded)

        return result
    return obj


# pylint: disable=redefined-builtin
def schema_from_object(name, object):
    """
        schema_from_object
    """
    properties = {}

    if isinstance(object, str):
        properties = {"example": "", "type": "string"}

    elif isinstance(object, int):
        properties = {"example": 0, "type": "integer"}

    elif isinstance(object, (datetime.datetime, datetime.date)):
        properties = {"example": str(k), "type": "string"}

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
                properties[k] = {"example": "", "type": "string"}
            else:  # isinstance(object, datetime.datetime):
                properties = {"example": str(k), "type": "string"}
                safrs.LOGGER.warning("Invalid schema object type %s", type(object))
    else:
        raise ValidationError("Invalid schema object type {}".format(type(object)))

    # generate a unique name to be used as a reference
    idx = _references.count(name)
    if idx:
        name = name + str(idx)
    # name = urllib.parse.quote(name)
    _references.append(name)
    return SchemaClassFactory(name, properties)


def get_swagger_doc_post_arguments(cls, method_name):
    """
        create a schema for all methods which can be called through the
        REST POST interface

        A method is called with following JSON payload:
        {
            "meta"   : {
                         "args" : {
                                    "parameter1" : "value1" ,
                                    "parameter2" : "value2" ,
                                  }
                       }
        }

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
            method_args = rest_doc.get("args", [])
            if method_args:
                model_name = "{}_{}".format(cls.__name__, method_name)
                method_field = {"method": method_name, "args": method_args}
                fields["meta"] = schema_from_object(model_name, method_field)

            parameters = rest_doc.get("parameters", [])
            if rest_doc.get(PAGEABLE):
                parameters += default_paging_parameters()
            if rest_doc.get(FILTERABLE):
                pass
        else:
            safrs.LOGGER.warning('No documentation for method "{}"'.format(method_name))
            # jsonapi_rpc method has no documentation, generate it w/ inspect
            f_args = inspect.getargspec(method).args
            f_defaults = inspect.getargspec(method).defaults or []
            if f_args[0] in ("cls", "self"):
                f_args = f_args[1:]
            args = dict(zip(f_args, f_defaults))
            model_name = "{}_{}".format(cls.__name__, method_name)
            model = SchemaClassFactory(model_name, [])
            arg_field = {"schema": model, "type": "string"}
            method_field = {"method": method_name, "args": args}
            fields["meta"] = schema_from_object(model_name, method_field)
            print(fields["meta"])

        return parameters, fields, description, method

    safrs.LOGGER.critical("Shouldnt get here ({})".format(method_name))


def swagger_method_doc(cls, method_name, tags=None):
    """
    swagger_method_doc
    """

    def swagger_doc_gen(func):

        class_name = cls.__name__
        if tags is None:
            doc_tags = [class_name]
        else:
            doc_tags = tags

        doc = {
            "tags": doc_tags,
            "description": "Invoke {}.{}".format(class_name, method_name),
            "summary": "Invoke {}.{}".format(class_name, method_name),
        }

        model_name = "{}_{}_{}".format("Invoke ", class_name, method_name)
        param_model = SchemaClassFactory(model_name, {})

        if func.__name__ == "get":
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
            # typically POST
            parameters, fields, description, method = get_swagger_doc_post_arguments(
                cls, method_name
            )
            """if inspect.ismethod(method) and method.__self__ is cls:
                # Mark classmethods: only these can be called when no {id} is given as parameter
                # in the swagger ui
                description += ' (classmethod)' """

            #
            # Retrieve the swagger schemas for the documented_api_methods
            #
            model_name = "{}_{}_{}".format(func.__name__, cls.__name__, method_name)
            param_model = SchemaClassFactory(model_name, fields)
            parameters.append(
                {
                    "name": model_name,
                    "in": "body",
                    "description": description,
                    "schema": param_model,
                    "required": True,
                }
            )

        # URL Path Parameter
        default_id = cls._s_sample_id()
        parameters.append(
            {
                "name": cls.object_id,  # parameter id, e.g. UserId
                "in": "path",
                "type": "string",
                "default": default_id,
                "required": True,
            }
        )
        doc["parameters"] = parameters
        doc["produces"] = ["application/json"]
        doc["responses"] = responses = {"200": {"description": "Success"}}

        return swagger.doc(doc)(func)

    return swagger_doc_gen


#
# Decorator is called when a swagger endpoint class is instantiated
# from API.expose_object eg.
#
def swagger_doc(cls, tags=None):
    """
    swagger_doc
    """

    def swagger_doc_gen(func):
        """
            Decorator used to document (SAFRSBase) class methods exposed in the API
        """
        default_id = cls._s_sample_id()
        class_name = cls.__name__
        table_name = cls.__tablename__
        http_method = func.__name__.lower()
        parameters = [
            {
                "name": cls.object_id,  # parameter id, e.g. UserId
                "in": "path",
                "type": "string",
                "default": default_id,
                "required": True,
            },
            {
                "name": "Content-Type",  # parameter id, e.g. UserId
                "in": "header",
                "type": "string",
                "default": "application/vnd.api+json",
                "required": True,
            },
        ]
        if tags is None:
            doc_tags = [table_name]
        else:
            doc_tags = tags

        doc = {"tags": doc_tags, "description": "Returns a {}".format(class_name)}

        responses = {}
        # adhere to open api
        model_name = "{}_{}".format(class_name, http_method)
        if http_method == "get":
            doc["summary"] = "Retrieve a {} object".format(class_name)
            _, responses = cls.get_swagger_doc(http_method)

        elif http_method == "post":
            _, responses = cls.get_swagger_doc(http_method)
            doc["summary"] = "Create a {} object".format(class_name)

            #
            # Create the default POST body schema
            #
            sample_dict = cls._s_sample_dict()
            sample_data = schema_from_object(
                model_name, {"data": {"attributes": sample_dict, "type": table_name}}
            )
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
            doc["summary"] = doc["description"] = "Delete a {} object".format(
                class_name
            )
            responses = {
                "204": {"description": "Object Deleted"},
                "404": {"description": "Object Not Found"},
            }

        elif http_method == "patch":
            doc["summary"] = "Update a {} object".format(class_name)
            post_model, responses = cls.get_swagger_doc("patch")
            sample = cls._s_sample_dict()
            sample_dict = cls._s_sample_dict()
            if sample:
                sample_data = schema_from_object(
                    model_name,
                    {
                        "data": {
                            "attributes": sample_dict,
                            "id": cls._s_sample_id(),
                            "type": table_name,
                        }
                    },
                )
            else:
                sample_data = schema_from_object(
                    model_name,
                    {
                        "data": {
                            "attributes": sample_dict,
                            "id": cls._s_sample_id(),
                            "type": table_name,
                        }
                    },
                )
            parameters.append(
                {
                    "name": "POST body",
                    "in": "body",
                    "description": "{} attributes".format(class_name),
                    "schema": sample_data,
                    "required": True,
                }
            )
        else:
            # one of 'options', 'head', 'patch'
            safrs.LOGGER.debug('no documentation for "%s" ', http_method)

        responses_str = {}
        for k, v in responses.items():
            # convert int response code to string
            responses_str[str(k)] = v

        doc["parameters"] = parameters
        doc["responses"] = responses_str
        doc["produces"] = ["application/json"]

        method_doc = parse_object_doc(func)
        safrs.dict_merge(doc, method_doc)

        return swagger.doc(doc)(func)

    return swagger_doc_gen


def get_sample_dict(sample):
    """
    get_sample_dict
    """
    if getattr(sample, "to_dict", False):
        # ==> isinstance SAFRSBASE
        sample_dict = sample.to_dict()
    else:
        cols = sample.__table__.columns
        sample_dict = {col.name: "" for col in cols if not col.name == "id"}
    return encode_schema(sample_dict)


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
        table_name = cls.__tablename__
        http_method = func.__name__.lower()
        #######################################################################
        # Following will only happen when exposing an exisiting DB
        #
        if not getattr(parent_class, "object_id", None):
            parent_class.object_id = parent_class.__name__ + "Id"
        if not getattr(child_class, "object_id", None):
            child_class.object_id = child_class.__name__ + "Id"
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
                "name": parent_class.object_id,
                "in": "path",
                "type": "string",
                "default": parent_class._s_sample_id(),
                "description": "{} item".format(parent_class.__name__),
                "required": True,
            },
            {
                "name": child_class.object_id,
                "in": "path",
                "type": "string",
                "default": child_class._s_sample_id(),
                "description": "{} item".format(class_name),
                "required": True,
            },
        ]

        parent_name = parent_class.__name__

        if tags is None:
            doc_tags = [table_name]
        else:
            doc_tags = tags

        doc = {
            "tags": doc_tags,
            "description": "Returns {} {} ids".format(
                parent_name, cls.relationship.key
            ),
        }

        responses = {}
        if http_method == "get":
            doc["summary"] = "Retrieve a {} object".format(class_name)
            _, responses = cls.get_swagger_doc(http_method)
        elif http_method in ("post", "patch"):
            _, responses = cls.get_swagger_doc(http_method)
            doc["summary"] = "Update {}".format(cls.relationship.key)
            doc["description"] = "Add a {} object to the {} relation on {}".format(
                child_class.__name__, cls.relationship.key, parent_name
            )
            sample_attrs = {}
            sample = getattr(cls, "sample", lambda: None)()
            if sample:
                sample_attrs = sample._s_sample_dict()
                sample_id = sample.id

            child_sample_id = child_class._s_sample_id()

            _, responses = child_class.get_swagger_doc("patch")
            data = {
                "type": child_class.__tablename__,
                "attributes": sample_attrs,
                "id": child_sample_id,
            }

            if cls.relationship.direction in (ONETOMANY, MANYTOMANY):
                data = [data]
            rel_post_schema = schema_from_object(
                "{}_Relationship".format(class_name), {"data": data}
            )
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
            doc["summary"] = "Delete from {} {}".format(
                parent_name, cls.relationship.key
            )
            doc["description"] = "Delete a {} object from the {} relation on {}".format(
                child_class.__name__, cls.relationship.key, parent_name
            )
            responses = {"204": {"description": "Object Deleted"}}

        else:
            # one of 'options', 'head', 'patch'
            safrs.LOGGER.info('no documentation for "%s" ', http_method)

        if http_method in ("patch",):
            # put_model, responses = child_class.get_swagger_doc(http_method)
            doc["summary"] = "Update a {} object".format(class_name)
            responses = {"201": {"description": "Object Updated"}}

        doc["parameters"] = parameters
        doc["responses"] = responses

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
