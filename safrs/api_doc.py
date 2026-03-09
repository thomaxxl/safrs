# Functions used to mark and inspect JSON:API RPC docs without importing
# Flask adapter-specific dependencies.
from __future__ import annotations

import inspect
from typing import Any, Callable, List, Optional

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
    obj_doc = str(inspect.getdoc(obj))
    raw_doc = obj_doc.split(DOC_DELIMITER)[0]
    yaml_doc: Any = None

    try:
        yaml_doc = yaml.safe_load(raw_doc)
    except (SyntaxError, yaml.scanner.ScannerError) as exc:
        safrs.log.error("Failed to parse documentation %s (%s)", raw_doc, exc)
        yaml_doc = {"description": raw_doc}
    except Exception as exc:
        raise SystemValidationError("Failed to parse api doc") from exc

    if isinstance(yaml_doc, dict):
        api_doc.update(yaml_doc)

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

