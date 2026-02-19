#
# # Functions for api documentation: these decorators generate the swagger schemas
# This should evolve to a more declarative version in the future with templates
#
import inspect
import datetime
import json
import flask
from http import HTTPStatus
import yaml  # type: ignore[import-untyped]
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOMANY, MANYTOONE
from flask_restful_swagger_2 import Schema, swagger
from safrs.errors import SystemValidationError
from safrs.config import get_config, is_debug
import safrs
from typing import Any, Callable, Dict, List, Optional, Union, cast


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
    HTTPStatus.INTERNAL_SERVER_ERROR.value: {"description": "Internal Server Error"},
}

# List to generate the swagger references / definitions unique name
# The _references will be added to the swagger in safrs
Schema._reference_count = []
Schema._references = {}


# pylint: disable=redefined-builtin,line-too-long,protected-access,logging-format-interpolation
def parse_object_doc(object: Callable) -> dict[str, Any]:
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
        safrs.log.error(f"Failed to parse documentation {raw_doc} ({exc})")
        yaml_doc = {"description": raw_doc}
    except Exception:
        raise SystemValidationError("Failed to parse api doc")

    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)

    return api_doc


def jsonapi_rpc(http_methods: Optional[List[str]] = None, valid_jsonapi: bool = True) -> Callable:
    """
    Decorator to expose functions in the REST API:
    When a method is decorated with jsonapi_rpc, this means
    it becomes available for use through HTTP POST (i.e. public)

    :param http_methods:
    :return: function
    """
    if http_methods is None:
        http_methods = ["POST"]

    def _documented_api_method(method: Any) -> Any:
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


def is_public(method: Any) -> Any:
    """
    :param method: SAFRSBase method
    :return: True or False, whether the method is to be exposed
    """

    return hasattr(method, REST_DOC)


def get_doc(method: Any) -> Any:
    """
    :param  method: SAFRSBase method
    :return: OAS documentation
    """

    return getattr(method, REST_DOC, None)


def get_http_methods(method: Any) -> Any:
    """
    :param method: SAFRSBase jsonapi_rpc method
    :return: a list of http methods used to call the method (e.g. POST)
    """

    return getattr(method, HTTP_METHODS, ["POST"])


def SchemaClassFactory(name: Any, properties: Any) -> Any:
    """
    Generate a Schema class, used to describe swagger schemas
    :param name: schema class name
    :param properties: class attributes
    :return: class
    """
    # generate a unique name to be used as a reference
    idx = Schema._reference_count.count(name)
    if idx:
        if Schema._references[name].properties == properties:
            return Schema._references[name]
        name = name + str(idx)

    for s_name, schema in Schema._references.items():
        if schema.properties == properties:
            # this detect duplicate schemas
            # ignore these for now
            pass

    Schema._reference_count.append(name)

    def __init__(self: Any, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            # here, the properties variable is the one passed to the
            # ClassFactory call
            if key not in properties:
                raise SystemValidationError(f"Argument {key} not valid for {self.__class__.__name__}")
            setattr(self, key, value)

    new_schema_cls = type(name, (Schema,), {"__init__": __init__, "properties": properties})
    cast(Any, new_schema_cls).description = ""
    Schema._references[name] = new_schema_cls
    return new_schema_cls


def encode_schema(obj: Any) -> Any:
    """
    None aka "null" is invalid in swagger schema definition
    This breaks our samples :/
    We don't add the item to the schema if it's None
    """
    result: Any = ""

    if obj is not None:
        try:
            result = json.loads(json.dumps(obj, cls=cast(Any, flask.current_app).json_encoder))
        except Exception as exc:
            safrs.log.warning(f"Json encoding failed for {obj}, type {type(obj)} ({exc})")
            result = str(obj)

    return result


# pylint: disable=redefined-builtin
def schema_from_object(name: Any, object: Any) -> Any:
    """
    :param name:
    :param object:
    :return: swagger schema object
    """

    properties: Any = {}

    if isinstance(object, str):
        properties = {"example": "", "type": "string"}

    elif isinstance(object, bool):
        properties = {"example": object, "type": "boolean"}

    elif isinstance(object, int):
        properties = {"example": 0, "type": "integer"}

    elif isinstance(object, (datetime.datetime, datetime.date, datetime.time)):
        properties = {"example": str(object), "type": "string"}

    elif isinstance(object, dict):
        for k, v in object.items():
            if isinstance(v, str):
                properties[k] = {"example": v, "type": "string"}
            elif isinstance(v, bool):
                properties[k] = {"example": v, "type": "boolean"}
            elif isinstance(v, int):
                properties[k] = {"example": v, "type": "integer"}
            elif isinstance(v, dict):
                properties[k] = {
                    "type": "object",
                    "additionalProperties": {},
                    "example": encode_schema(v),
                }
            elif isinstance(v, list):
                item_schema: dict[str, Any] = {}
                if v and isinstance(v[0], dict):
                    item_schema = {"type": "object", "additionalProperties": {}}
                properties[k] = {
                    "type": "array",
                    "items": item_schema,
                    "example": encode_schema(v),
                }
            elif v is None:
                # swagger doesn't allow null values
                properties[k] = {"example": "", "type": "string"}
            else:  # isinstance(object, datetime.datetime):
                properties = {"example": str(k), "type": "string"}
                safrs.log.warning("Invalid schema object type %s", type(object))
    else:
        raise SystemValidationError(f"Invalid schema object type {type(object)}")

    properties = encode_schema(properties)
    schema = SchemaClassFactory(name, properties)
    return schema


def update_response_schema(responses: Any) -> None:
    """
    Add predefined response schemas if none is available yet
    """
    http_codes = {str(status.value): status.description for status in HTTPStatus}
    for code, response in responses.items():
        if response and not response.get("schema") and int(code) >= 400:
            jsonapi_error = {"errors": [{"title": http_codes.get(code, ""), "detail": "", "code": code}]}
            err_schema = schema_from_object(f"jsonapi_error_{code}", jsonapi_error)
            responses[code]["schema"] = err_schema


def _find_method_on_class(cls: Any, method_name: Any) -> Any:
    for name, method in inspect.getmembers(cls):
        if name == method_name:
            return method
    raise SystemValidationError(f"method {method_name} not found")


def _populate_post_method_fields(cls: Any, method: Any, method_name: Any, http_method: Any, fields: dict[str, Any], rest_doc: dict[str, Any]) -> list[Any]:
    parameters = rest_doc.get("parameters", [])
    method_args = rest_doc.get("args", [])
    if method_args and isinstance(method_args, dict) and http_method == "post":
        model_name = f"{cls.__name__}_{method_name}"
        method_field = {"method": method_name, "args": method_args}
        if getattr(method, "valid_jsonapi", True):
            fields["meta"] = schema_from_object(model_name, method_field)
        else:
            for k, v in method_args.items():
                fields[k] = {"example": v}
    return parameters


def _append_filterable_parameters(cls: Any, parameters: list[Any], description: str) -> None:
    for column_name, column in cls._s_column_dict.items():
        if getattr(column, "expose", True) and getattr(column, FILTERABLE, True):
            desc = getattr(column, "description", f"{column_name} attribute filter (csv)")
            param = {
                "default": "",
                "type": "string",
                "name": f"filter[{column_name}]",
                "in": "query",
                "format": "string",
                "required": False,
                "description": desc,
            }
            parameters += param  # type: ignore[arg-type]


def _populate_undocumented_method_fields(method: Any, cls: Any, method_name: Any, http_method: Any, f_args: list[str], fields: dict[str, Any]) -> None:
    if not f_args or http_method == "options":
        return
    safrs.log.warning(f'No documentation for method "{method_name}"')
    f_defaults: list[Any] = list(inspect.getfullargspec(method).defaults or [])
    if f_args and f_args[0] in ("cls", "self"):
        f_args = f_args[1:]
    args = dict(zip(f_args, f_defaults))
    model_name = f"{cls.__name__}_{method_name}"
    method_field = {"method": method_name, "args": args}
    if getattr(method, "valid_jsonapi", True):
        fields["meta"] = schema_from_object(model_name, method_field)


def _normalize_parameters(parameters: list[Any]) -> None:
    for param in parameters:
        if param.get("in") is None:
            param["in"] = "query"
        if param.get("type") is None:
            param["type"] = "string"


def get_swagger_doc_arguments(cls: Any, method_name: Any, http_method: Any) -> Any:
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

    The schema is created using the values from the jsonapi_rpc decorator,
    returned by get_doc()

    We use "meta" to remain compliant with the jsonapi schema
    """

    parameters: list[Any] = []
    fields: dict[str, Any] = {}
    method = _find_method_on_class(cls, method_name)
    f_args = inspect.getfullargspec(method).args
    rest_doc = cast(Optional[dict[str, Any]], get_doc(method))
    description = ""
    if rest_doc is not None:
        description = rest_doc.get("description", "")
        parameters = _populate_post_method_fields(cls, method, method_name, http_method, fields, rest_doc)
        if rest_doc.get(PAGEABLE):
            parameters += default_paging_parameters()
        if rest_doc.get(FILTERABLE):
            _append_filterable_parameters(cls, parameters, description)
    else:
        _populate_undocumented_method_fields(method, cls, method_name, http_method, f_args, fields)

    _normalize_parameters(parameters)

    return parameters, fields, description, method


#
# Decorator is called when a swagger endpoint class is instantiated
# from API.expose_object eg.
#
def swagger_doc(cls: Any, tags: Any=None) -> Any:
    """
    swagger_doc
    """

    def swagger_doc_gen(func: Any, instance: Any=False) -> Any:
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

        doc: dict[str, Any] = {"tags": doc_tags}

        responses = {}
        # adhere to open api
        # the model_name will hold the OAS "$ref" schema reference
        coll_model_name = f"{class_name}_coll"  # collection model name
        inst_model_name = f"{class_name}_inst"  # instance model name

        sample_dict = cls._s_sample_dict()

        # Samples with "id" are used for GET and PATCH
        sample_instance = {"attributes": sample_dict, "type": cls._s_type, "id": cls._s_sample_id()}

        if http_method == "get":
            sample_rels: dict[str, Any] = {}
            for rel_name, val in cls._s_relationships.items():
                sample_rels[rel_name] = {"data": None if val.direction is MANYTOONE else [], "links": {"self": None}}
            sample_instance["relationships"] = sample_rels

        coll_sample_data = schema_from_object(coll_model_name, {"data": [sample_instance]})
        coll_sample_data.description += f"{class_name} {http_method};"

        inst_sample_data = schema_from_object(inst_model_name, {"data": sample_instance})
        inst_sample_data.description += f"{class_name} {http_method};"

        cls.swagger_models["instance"] = inst_sample_data
        cls.swagger_models["collection"] = coll_sample_data

        if http_method == "get":
            doc["summary"] = f"Retrieve a {class_name} object"
            doc["collection_summary"] = f"Retrieve a collection of {class_name} objects"
            body, responses = cls._s_get_swagger_doc(http_method)
            responses[HTTPStatus.OK.value] = {"schema": coll_sample_data, "description": HTTPStatus.OK.description}

        elif http_method == "patch":
            post_model, responses = cls._s_get_swagger_doc(http_method)
            parameters.append(
                {
                    "name": "PATCH body",
                    "in": "body",
                    "description": f"{class_name} attributes",
                    "schema": inst_sample_data,
                    "required": True,
                }
            )
            responses[HTTPStatus.OK.value] = {"schema": inst_sample_data, "description": HTTPStatus.OK.description}

        elif http_method == "post":
            _, responses = cls._s_get_swagger_doc(http_method)
            doc["summary"] = f"Create a {class_name} object"
            # Create the default POST body schema
            sample_dict = cls._s_sample_dict()
            # The POST sample doesn't contain an "id", unless cls.allow_client_generated_ids is True
            if cls.allow_client_generated_ids:
                sample_data = schema_from_object(
                    inst_model_name, {"data": {"attributes": sample_dict, "type": cls._s_type, "id": "client_generated"}}
                )
            else:
                sample_data = schema_from_object(inst_model_name, {"data": {"attributes": sample_dict, "type": cls._s_type}})

            sample_data.description += f"{class_name} {http_method};"

            parameters.append(
                {"name": "POST body", "in": "body", "description": f"{class_name} attributes", "schema": sample_data, "required": True}
            )
            responses[HTTPStatus.CREATED.value] = {"schema": inst_sample_data, "description": HTTPStatus.CREATED.description}

        elif http_method == "delete":
            _, responses = cls._s_get_swagger_doc(http_method)
        elif http_method != "options":
            # one of 'options', 'head', 'delete'
            safrs.log.debug(f'no additional documentation for "{func}" ')

        if is_debug():
            responses.update(debug_responses)

        doc["parameters"] = parameters
        doc["responses"] = responses
        doc["produces"] = ["application/vnd.api+json"]

        method_doc = parse_object_doc(func)
        safrs.dict_merge(doc, method_doc)
        apply_fstring(doc, locals())
        update_response_schema(doc["responses"])
        return swagger.doc(doc)(func)

    return swagger_doc_gen


def _ensure_relationship_swagger_attrs(parent_class: Any, child_class: Any) -> None:
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


def _relationship_parameters(parent_class: Any, child_class: Any, class_name: str) -> list[dict[str, Any]]:
    return [
        {
            "name": parent_class._s_object_id,
            "in": "path",
            "type": "string",
            "default": parent_class._s_sample_id(),
            "description": f"{parent_class.__name__} item",
            "required": True,
        },
        {
            "name": child_class._s_object_id,
            "in": "path",
            "type": "string",
            "default": child_class._s_sample_id(),
            "description": f"{class_name} item",
            "required": True,
        },
    ]


def _relationship_model_name(relationship: Any, class_name: str) -> str:
    if relationship.direction in (ONETOMANY, MANYTOMANY):
        return f"{class_name}_rel_coll"
    return f"{class_name}_rel_inst"


def _relationship_data_payload(relationship: Any, child_class: Any) -> Any:
    data: Any = {"type": child_class._s_type, "id": child_class._s_sample_id()}
    if relationship.direction in (ONETOMANY, MANYTOMANY):
        return [data]
    return data


def _append_relationship_body_param(parameters: list[Any], class_name: str, schema: Any) -> None:
    parameters.append(
        {
            "name": f"{class_name} body",
            "in": "body",
            "description": f"{class_name} POST model",
            "schema": schema,
            "required": True,
        }
    )


def _relationship_responses_and_parameters(
    cls: Any,
    relationship: Any,
    http_method: str,
    child_class: Any,
    class_name: str,
    model_name: str,
    parameters: list[Any],
) -> dict[Any, Any]:
    responses: dict[Any, Any] = {}
    if http_method == "get":
        _, responses = cls._s_get_swagger_doc(http_method)
        return responses

    if http_method in ("post", "patch"):
        _, responses = cls._s_get_swagger_doc(http_method)
        _, responses = child_class._s_get_swagger_doc("patch")
        data = _relationship_data_payload(relationship, child_class)
        if relationship.direction in (ONETOMANY, MANYTOMANY):
            responses.pop(HTTPStatus.OK.value, None)
        rel_post_schema = schema_from_object(model_name, {"data": data})
        rel_post_schema.description += f"{class_name} {http_method} relationship;"
        cls.swagger_models["instance"] = rel_post_schema
        cls.swagger_models["collection"] = rel_post_schema
        _append_relationship_body_param(parameters, class_name, rel_post_schema)
        if relationship.direction is MANYTOONE:
            responses[HTTPStatus.OK.value] = {"schema": rel_post_schema, "description": HTTPStatus.OK.description}
        return responses

    if http_method == "delete":
        _, responses = child_class._s_get_swagger_doc("patch")
        rel_del_schema = schema_from_object(model_name, {"data": _relationship_data_payload(relationship, child_class)})
        _append_relationship_body_param(parameters, class_name, rel_del_schema)
        return responses

    if http_method != "options":
        safrs.log.info(f'no documentation for "{http_method}" ')
    return responses


def swagger_relationship_doc(cls: Any, tags: Any=None) -> Any:
    """
    swagger_relationship_doc
    """

    def swagger_doc_gen(func: Any) -> Any:
        """
        Decorator used to document relationship methods exposed in the API
        """

        parent_class = cls.relationship.parent.class_
        child_class = cls.relationship.mapper.class_
        class_name = cls.__name__
        http_method = func.__name__.lower()
        _ensure_relationship_swagger_attrs(parent_class, child_class)

        parameters = _relationship_parameters(parent_class, child_class, class_name)
        doc_tags = [cls._s_collection_name] if tags is None else tags
        doc: dict[str, Any] = {"tags": doc_tags}
        doc.update(parse_object_doc(func))
        relationship = cls.relationship
        model_name = _relationship_model_name(relationship, class_name)
        responses = _relationship_responses_and_parameters(cls, relationship, http_method, child_class, class_name, model_name, parameters)

        doc["parameters"] = parameters
        if doc.get("responses"):
            responses.update({str(val): desc for val, desc in doc["responses"].items()})
        if is_debug():
            responses.update(debug_responses)
        doc["responses"] = responses

        parent_name = parent_class.__name__
        child_name = child_class.__name__
        direction = "to-many" if relationship.direction in (ONETOMANY, MANYTOMANY) else "to-one"
        apply_fstring(doc, locals())
        update_response_schema(doc["responses"])
        return swagger.doc(doc)(func)

    return swagger_doc_gen


def swagger_method_doc(cls: Any, method_name: Any, tags: Any=None) -> Any:
    """
    Generate decorator used to document SAFRSJSONRPCAPI instances
    """

    def swagger_doc_gen(func: Any) -> Any:
        """
        decorator
        """
        method = getattr(cls, method_name, None)
        method_doc = parse_object_doc(cast(Any, method))
        class_name = cls.__name__
        if tags is None:
            doc_tags = [cls._s_collection_name]
        else:
            doc_tags = tags

        responses = method_doc.get("responses", {HTTPStatus.OK.value: {"description": HTTPStatus.OK.description}})
        if is_debug():
            responses.update(debug_responses)

        summary = method_doc.get("summary", f"Invoke {class_name}.{method_name}")
        description = method_doc.get("description", summary)

        doc = {"tags": doc_tags, "description": description, "summary": summary, "responses": responses}

        model_name = f"Invoke _{class_name}_{method_name}"
        param_model = SchemaClassFactory(model_name, {})
        parameters, fields, description, method = get_swagger_doc_arguments(cls, method_name, http_method=func.__name__)

        if func.__name__ == "get":
            if not parameters:
                parameters = [
                    {"name": "varargs", "in": "query", "description": f"{method_name} arguments", "required": False, "type": "string"}
                ]
        else:
            # Retrieve the swagger schemas for the jsonapi_rpc methods from the docstring
            parameters, fields, description, method = get_swagger_doc_arguments(cls, method_name, http_method=func.__name__)
            model_name = f"{func.__name__}_{cls.__name__}_{method_name}"
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


def default_paging_parameters() -> list[dict[str, Any]]:
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


def apply_fstring(swagger_obj: Any, vars: Any, k: Any=None) -> Any:
    """
    Format the f-strings in the swagger object
    """
    if isinstance(swagger_obj, str):
        result = swagger_obj
        try:
            result = swagger_obj.format(**vars)
        except Exception as exc:
            safrs.log.error(f"Failed to format ({exc})")
        return result
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
