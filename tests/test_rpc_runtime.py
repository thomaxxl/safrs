from __future__ import annotations

from typing import Any

import pytest

from safrs import SAFRSFormattedResponse
from safrs.api_doc import get_doc, get_http_methods, jsonapi_rpc as api_jsonapi_rpc, resolve_rpc_method
from safrs.errors import ValidationError
from safrs.rpc import normalize_rpc_result, parse_rpc_args, unwrap_formatted_response
from safrs.swagger_doc import jsonapi_rpc as swagger_jsonapi_rpc
from safrs import api_doc, swagger_doc


def test_rpc_doc_helpers_use_api_doc_as_single_source_of_truth() -> None:
    assert swagger_doc.jsonapi_rpc is api_doc.jsonapi_rpc
    assert swagger_doc.get_doc is api_doc.get_doc
    assert swagger_doc.get_http_methods is api_doc.get_http_methods
    assert swagger_doc.parse_object_doc is api_doc.parse_object_doc
    assert swagger_doc.resolve_rpc_method is api_doc.resolve_rpc_method


def test_parse_object_doc_plain_text_maps_to_description() -> None:
    def documented() -> None:
        """Plain text RPC description."""

    assert api_doc.parse_object_doc(documented) == {"description": "Plain text RPC description."}


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


def test_resolve_rpc_method_finds_inherited_rpc_method() -> None:
    class RPCMixin:
        @classmethod
        @api_jsonapi_rpc(http_methods=["GET"])
        def inherited(cls) -> None:
            """description: inherited rpc"""

    class Child(RPCMixin):
        pass

    method = resolve_rpc_method(Child, "inherited")
    assert method.__name__ == "inherited"
    assert get_http_methods(method) == ["GET"]
    assert get_doc(method)["description"] == "inherited rpc"


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


def test_parse_rpc_args_rejects_invalid_payload_shapes() -> None:
    with pytest.raises(ValidationError) as invalid_jsonapi_payload:
        parse_rpc_args(
            http_method="POST",
            valid_jsonapi=True,
            query_items=[],
            payload=["not", "an", "object"],
        )
    assert "Invalid JSON:API payload (expected object)" in invalid_jsonapi_payload.value.message

    with pytest.raises(ValidationError) as invalid_meta:
        parse_rpc_args(
            http_method="POST",
            valid_jsonapi=True,
            query_items=[],
            payload={"meta": "not-an-object"},
        )
    assert "Invalid JSON:API RPC payload: 'meta' must be an object" in invalid_meta.value.message

    with pytest.raises(ValidationError) as invalid_plain_payload:
        parse_rpc_args(
            http_method="POST",
            valid_jsonapi=False,
            query_items=[],
            payload=["not", "an", "object"],
        )
    assert "Invalid RPC payload (expected object)" in invalid_plain_payload.value.message


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

    single_resource_payload = normalize_rpc_result(
        Resource(),
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert single_resource_payload["data"] == {"type": "Resource", "id": "1"}

    passthrough_payload = normalize_rpc_result(
        {"data": {"type": "Resource", "id": "1"}, "meta": {"ok": True}, "links": {"self": "/rpc"}},
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert passthrough_payload["data"] == {"type": "Resource", "id": "1"}
    assert passthrough_payload["meta"] == {"ok": True}
    assert passthrough_payload["links"] == {"self": "/rpc"}

    scalar_payload = normalize_rpc_result(
        7,
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert scalar_payload == {"meta": {"result": 7}}

    list_payload = normalize_rpc_result(
        ["a", "b"],
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert list_payload == {"meta": {"result": ["a", "b"]}}

    none_payload = normalize_rpc_result(
        None,
        valid_jsonapi=True,
        encode_value=encode_value,
        encode_resource=encode_resource,
        jsonapi_doc=jsonapi_doc,
    )
    assert none_payload == {"meta": {}}


def test_unwrap_formatted_response_uses_real_type_check() -> None:
    response = object.__new__(SAFRSFormattedResponse)
    response.response = {"meta": {"result": "wrapped"}}
    assert unwrap_formatted_response(response) == {"meta": {"result": "wrapped"}}
    assert unwrap_formatted_response({"meta": {"result": "raw"}}) == {"meta": {"result": "raw"}}
