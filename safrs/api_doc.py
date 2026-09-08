# Functions used to mark and inspect JSON:API RPC docs without importing
# Flask adapter-specific dependencies.
from __future__ import annotations

import datetime
import inspect
from typing import Any, Callable, Dict, List, Optional

import yaml  # type: ignore[import-untyped]

import safrs
from .config import get_config
from .errors import SystemValidationError

REST_DOC = "__rest_doc"
HTTP_METHODS = "__http_method"
DOC_DELIMITER = "---"
PAGEABLE = "pageable"
FILTERABLE = "filterable"


def parse_object_doc(obj: Callable[..., Any]) -> dict[str, Any]:
    """
    Parse the yaml description from documented methods.
    """
    api_doc: dict[str, Any] = {}
    obj_doc = inspect.getdoc(obj) or ""
    raw_doc = obj_doc.split(DOC_DELIMITER)[0]
    yaml_doc: Any = None

    if not raw_doc.strip():
        return api_doc

    try:
        yaml_doc = yaml.safe_load(raw_doc)
    except (SyntaxError, yaml.YAMLError) as exc:
        # Documentation strings may contain examples or credentials.  Log only
        # the failure type so malformed documentation cannot disclose content.
        safrs.log.error("Failed to parse documentation (%s)", type(exc).__name__)
        yaml_doc = {"description": raw_doc}
    except Exception as exc:
        raise SystemValidationError("Failed to parse api doc") from exc

    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)
    elif raw_doc.strip():
        api_doc["description"] = raw_doc.strip()

    return api_doc


def jsonapi_rpc(http_methods: Optional[List[str]] = None, valid_jsonapi: bool = True) -> Callable[[Any], Any]:
    """
    Decorator to expose functions in the REST API.
    """
    if http_methods is None:
        http_methods = ["POST"]

    def _documented_api_method(method: Any) -> Any:
        use_api_methods = get_config("USE_API_METHODS")
        if use_api_methods:
            try:
                api_doc = parse_object_doc(method)
            except yaml.scanner.ScannerError:
                safrs.log.error("Failed to parse documentation for %s", method)
                api_doc = {}
            setattr(method, REST_DOC, api_doc)
            setattr(method, HTTP_METHODS, http_methods)
            setattr(method, "valid_jsonapi", valid_jsonapi)
        return method

    return _documented_api_method


def is_public(method: Any) -> bool:
    """
    Whether a SAFRSBase method is exposed through jsonapi_rpc.
    """
    return hasattr(method, REST_DOC)


def get_doc(method: Any) -> Any:
    """
    Return OAS documentation metadata for a jsonapi_rpc method.
    """
    return getattr(method, REST_DOC, None)


def get_http_methods(method: Any) -> Any:
    """
    Return the HTTP methods configured by jsonapi_rpc.
    """
    return getattr(method, HTTP_METHODS, ["POST"])


def resolve_rpc_method(cls: Any, method_name: str) -> Any:
    """
    Resolve a method without triggering descriptor evaluation on unrelated attrs.
    """
    for name in dir(cls):
        if name != method_name:
            continue
        method = inspect.getattr_static(cls, name)
        if isinstance(method, (classmethod, staticmethod)):
            return method.__func__
        return method
    raise SystemValidationError(f"method {method_name} not found")


def schema_for_example_value(value: Any) -> Dict[str, Any]:
    """
    Generate a lightweight OpenAPI schema fragment from an example value.
    """
    if isinstance(value, bool):
        return {"type": "boolean", "example": value}
    if isinstance(value, int):
        return {"type": "integer", "example": value}
    if isinstance(value, float):
        return {"type": "number", "example": value}
    if isinstance(value, datetime.datetime):
        return {"type": "string", "format": "date-time", "example": value.isoformat(" ")}
    if isinstance(value, datetime.date):
        return {"type": "string", "format": "date", "example": value.isoformat()}
    if isinstance(value, datetime.time):
        return {"type": "string", "example": value.isoformat()}
    if isinstance(value, dict):
        return {"type": "object", "additionalProperties": True, "example": value}
    if isinstance(value, list):
        return {"type": "array", "items": {}, "example": value}
    return {"type": "string", "example": str(value) if value is not None else ""}


def jsonapi_rpc_meta_schema(method_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the JSON:API RPC request schema for ``meta.args``.
    """
    args_properties = {
        arg_name: schema_for_example_value(arg_value)
        for arg_name, arg_value in method_args.items()
    }
    args_schema: Dict[str, Any] = {"type": "object", "additionalProperties": True}
    if args_properties:
        args_schema["properties"] = args_properties
    return {
        "type": "object",
        "required": ["args"],
        "properties": {"args": args_schema},
        "additionalProperties": False,
    }
