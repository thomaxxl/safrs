from __future__ import annotations

from typing import Any

from safrs.api_doc import get_doc, get_http_methods, jsonapi_rpc as api_jsonapi_rpc, resolve_rpc_method
from safrs.rpc import normalize_rpc_result, parse_rpc_args
from safrs.swagger_doc import jsonapi_rpc as swagger_jsonapi_rpc


def test_jsonapi_rpc_import_paths_attach_identical_metadata() -> None:
    @api_jsonapi_rpc(http_methods=["GET"], valid_jsonapi=False)
    def from_api_doc() -> None:
        """description: from api_doc"""

    @swagger_jsonapi_rpc(http_methods=["GET"], valid_jsonapi=False)
    def from_swagger_doc() -> None:
        """description: from swagger_doc"""

    assert get_http_methods(from_api_doc) == ["GET"]
    assert get_http_methods(from_swagger_doc) == ["GET"]
    assert get_doc(from_api_doc)["description"] == "from api_doc"
    assert get_doc(from_swagger_doc)["description"] == "from swagger_doc"
    assert getattr(from_api_doc, "valid_jsonapi") is False
    assert getattr(from_swagger_doc, "valid_jsonapi") is False


def test_resolve_rpc_method_uses_static_lookup_for_decorated_members() -> None:
    class Example:
        @classmethod
        @api_jsonapi_rpc(http_methods=["POST"])
        def ping(cls) -> None:
            return None

    method = resolve_rpc_method(Example, "ping")
    assert method.__name__ == "ping"
    assert get_http_methods(method) == ["POST"]


def test_parse_rpc_args_uses_shared_contract() -> None:
    get_args = parse_rpc_args(
        http_method="GET",
        valid_jsonapi=True,
        query_items=[
            ("name", "alpha"),
            ("include", "books"),
            ("fields[Thing]", "name"),
            ("filter[name]", "alpha"),
            ("page[offset]", "0"),
        ],
        payload={"meta": {"args": {"name": "ignored"}}},
    )
    assert get_args == {"name": "alpha"}

    post_args = parse_rpc_args(
        http_method="POST",
        valid_jsonapi=True,
        query_items=[("name", "query")],
        payload={"meta": {"args": {"name": "body"}}},
    )
    assert post_args == {"name": "body"}

    plain_args = parse_rpc_args(
        http_method="POST",
        valid_jsonapi=False,
        query_items=[("message", "query")],
        payload={"message": "body"},
    )
    assert plain_args == {"message": "body"}


def test_normalize_rpc_result_handles_plain_and_resource_payloads() -> None:
    class Resource:
        _s_type = "Resource"
        jsonapi_id = "1"

    def encode_value(value: Any) -> Any:
        if isinstance(value, list):
            return [encode_value(item) for item in value]
        if isinstance(value, Resource):
            return {"type": value._s_type, "id": value.jsonapi_id}
        return value

    def encode_resource(value: Any) -> Any:
        return {"type": value._s_type, "id": value.jsonapi_id}

    def jsonapi_doc(data: Any = None, errors: Any = None, included: Any = None, meta: Any = None) -> dict[str, Any]:
        doc: dict[str, Any] = {}
        if data is not None:
            doc["data"] = data
        if errors is not None:
            doc["errors"] = errors
        if included is not None:
            doc["included"] = included
        if meta is not None:
            doc["meta"] = meta
        return doc

    assert normalize_rpc_result(
        {"raw": True},
        valid_jsonapi=False,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    ) == {"raw": True}

    resource_payload = normalize_rpc_result(
        [Resource()],
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert resource_payload["data"] == [{"type": "Resource", "id": "1"}]
