from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Tuple

from .errors import ValidationError

JSONAPI_DOCUMENT_KEYS = frozenset({"data", "errors", "meta", "included", "links", "jsonapi"})
_RESERVED_QUERY_KEYS = frozenset({"include", "sort", "filter", "page[offset]", "page[limit]", "page[number]", "page[size]"})


def is_reserved_rpc_query_param(name: str) -> bool:
    """
    JSON:API transport parameters should not be forwarded as RPC kwargs.
    """
    return (
        name in _RESERVED_QUERY_KEYS
        or (name.startswith("fields[") and name.endswith("]"))
        or (name.startswith("filter[") and name.endswith("]"))
    )


def parse_rpc_args(
    *,
    http_method: str,
    valid_jsonapi: bool,
    query_items: Iterable[Tuple[str, Any]],
    payload: Any,
) -> Dict[str, Any]:
    """
    Parse RPC args with one adapter-independent contract.

    - GET is query-only and ignores the request body.
    - JSON:API body methods read ``meta.args``.
    - ``valid_jsonapi=False`` body methods read the raw JSON object.
    - Reserved JSON:API query params are never forwarded as user kwargs.
    """
    method = str(http_method).upper()
    if method == "GET":
        return {
            str(key): value
            for key, value in query_items
            if not is_reserved_rpc_query_param(str(key))
        }

    if valid_jsonapi:
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValidationError("Invalid JSON:API payload (expected object)")

        meta = payload.get("meta", None)
        if meta is None:
            return {}
        if not isinstance(meta, dict):
            raise ValidationError("Invalid JSON:API RPC payload: 'meta' must be an object")

        meta_args = meta.get("args", {})
        if meta_args is None:
            return {}
        if not isinstance(meta_args, dict):
            raise ValidationError("Invalid JSON:API RPC payload: 'meta.args' must be an object")
        return {str(key): value for key, value in meta_args.items()}

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValidationError("Invalid RPC payload (expected object)")
    return {str(key): value for key, value in payload.items()}


def is_invalid_rpc_args_error(exc: TypeError) -> bool:
    message = str(exc)
    markers = (
        "unexpected keyword argument",
        "required positional argument",
        "positional argument",
        "multiple values for argument",
    )
    return any(marker in message for marker in markers)


def is_jsonapi_document(payload: Any) -> bool:
    return isinstance(payload, Mapping) and any(key in payload for key in JSONAPI_DOCUMENT_KEYS)


def is_resource_instance(value: Any) -> bool:
    return hasattr(value, "_s_type") and hasattr(value, "jsonapi_id")


def normalize_rpc_result(
    result: Any,
    *,
    valid_jsonapi: bool,
    encode_value: Callable[[Any], Any],
    encode_resource: Callable[[Any], Any],
    jsonapi_doc: Callable[..., Dict[str, Any]],
) -> Any:
    """
    Normalize RPC results for both Flask and FastAPI adapters.
    """
    payload = result.response if result.__class__.__name__ == "SAFRSFormattedResponse" and hasattr(result, "response") else result

    if is_jsonapi_document(payload):
        document = jsonapi_doc(
            data=encode_value(payload.get("data")) if "data" in payload else None,
            errors=payload.get("errors"),
            included=encode_value(payload.get("included")) if "included" in payload else None,
            meta=payload.get("meta"),
        )
        if payload.get("links") is not None:
            document["links"] = payload["links"]
        return document

    if valid_jsonapi is False:
        return encode_value(payload)

    if is_resource_instance(payload):
        return jsonapi_doc(data=encode_resource(payload))

    if isinstance(payload, (list, tuple, set)):
        items = list(payload)
        if items and all(is_resource_instance(item) for item in items):
            return jsonapi_doc(data=[encode_resource(item) for item in items])
        return jsonapi_doc(meta={"result": encode_value(items)})

    if payload is None:
        return jsonapi_doc(meta={})

    return jsonapi_doc(meta={"result": encode_value(payload)})
