from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from safrs.errors import ValidationError
from safrs.filtering import jsonapi_filter_fields
from safrs.fastapi.api import JSONAPIHTTPError, SafrsFastAPI, install_jsonapi_exception_handlers
from safrs.jsonapi_context import maybe_jsonapi_context


def _request(path: str = "/", query: str = "", method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": query.encode(),
        }
    )


class _SortModel:
    _s_type = "Order"
    _s_collection_name = "Order"
    _s_jsonapi_attrs = {"CustomerId": object(), "OrderDate": object(), "CategoryId": object(), "id": object()}
    id = object()
    CategoryId = object()

    class id_type:
        primary_keys = ["id"]

        @staticmethod
        def validate_id(value: Any) -> int:
            return int(value)


class _IncludeRelationship:
    expose = True
    mapper = SimpleNamespace(class_=object)


class _IncludeModel:
    _s_type = "Category"
    _s_class_name = "Category"
    _s_relationships = {
        "Products": _IncludeRelationship(),
        "Suppliers": _IncludeRelationship(),
    }


class _PatchObject:
    def __init__(self) -> None:
        self.jsonapi_id = "1"

    def _s_patch(self, **_attrs: Any) -> _PatchObject:
        return self

    def _s_meta(self) -> dict[str, Any]:
        return {}

    def _s_jsonapi_encode(self) -> dict[str, Any]:
        return {
            "type": "Thing",
            "id": "1",
            "attributes": {},
            "links": {"self": "/Thing/1/"},
            "relationships": {},
        }


class _PatchModel:
    _s_type = "Thing"
    _s_collection_name = "Thing"
    _s_jsonapi_attrs: dict[str, Any] = {}

    class id_type:
        primary_keys = ["Id"]

        @staticmethod
        def validate_id(value: Any) -> int:
            return int(value)

    @staticmethod
    def get_instance(_object_id: Any) -> _PatchObject:
        return _PatchObject()


def test_request_validation_errors_are_mapped_to_422_jsonapi() -> None:
    app = FastAPI()
    install_jsonapi_exception_handlers(app)
    handler = app.exception_handlers[RequestValidationError]
    request = _request()
    exc = RequestValidationError([{"loc": ("body", "data"), "msg": "Field required", "type": "missing"}])

    response = asyncio.run(handler(request, exc))

    assert response.status_code == 422
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["errors"][0]["status"] == "422"


def test_pagination_args_support_page_number_and_size() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    request = _request("/api/Order/", "page[number]=2&page[size]=5")

    page_offset, page_limit = api._pagination_args(request)
    paged_items = api._apply_pagination(list(range(1, 21)), request)

    assert page_offset == 5
    assert page_limit == 5
    assert paged_items == [6, 7, 8, 9, 10]


def test_openapi_query_params_include_page_number_and_size() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    params = api._jsonapi_query_parameters(_SortModel, include_pagination=True)
    names = {str(param.get("name", "")) for param in params}

    assert "page[offset]" in names
    assert "page[limit]" in names
    assert "page[number]" in names
    assert "page[size]" in names


def test_openapi_include_query_param_description_lists_relationship_examples() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    params = api._jsonapi_query_parameters(_IncludeModel, include_include=True)
    include_param = next(param for param in params if str(param.get("name")) == "include")

    assert include_param["description"] == "Category relationships to include (csv, ex.: Products,Suppliers)"


def test_sort_supports_multi_sort_and_default_id() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    items = [
        SimpleNamespace(id=3, CustomerId=2, OrderDate="2024-01-01"),
        SimpleNamespace(id=1, CustomerId=1, OrderDate="2024-01-01"),
        SimpleNamespace(id=2, CustomerId=1, OrderDate="2024-02-01"),
    ]

    multi_sorted = api._apply_sort_query_or_items(
        _SortModel,
        items,
        _request("/api/Order/", "sort=CustomerId,-OrderDate"),
    )
    default_sorted = api._apply_sort_query_or_items(_SortModel, items, _request("/api/Order/", ""))

    assert [item.id for item in multi_sorted] == [2, 1, 3]
    assert [item.id for item in default_sorted] == [1, 2, 3]


def test_bracket_filter_csv_in_behavior_on_collections() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    items = [
        SimpleNamespace(CategoryId=1),
        SimpleNamespace(CategoryId=2),
        SimpleNamespace(CategoryId=3),
    ]

    filtered = api._apply_filter(_SortModel, _request("/api/Product/", "filter[CategoryId]=1,2"), items)

    assert [item.CategoryId for item in filtered] == [1, 2]


def test_bracket_filter_rejects_fields_outside_jsonapi_read_attributes() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    items = [SimpleNamespace(secret="hunter2"), SimpleNamespace(secret="decoy")]

    with pytest.raises(ValidationError) as exc:
        api._apply_filter(_SortModel, _request("/api/Order/", "filter[secret]=hunter2"), items)
    assert "unknown attribute" in exc.value.message


def test_bracket_filter_applies_instance_level_read_permissions() -> None:
    class _TypedAttribute:
        type = SimpleNamespace(python_type=str)

    class _InstanceScopedModel:
        secret = _TypedAttribute()
        _s_jsonapi_attrs = {"secret": secret}

        def __init__(self, object_id: int, secret: str) -> None:
            self.id = object_id
            self.secret = secret

        def _s_check_perm(self, property_name: str, permission: str = "r") -> bool:
            return not (property_name == "secret" and permission == "r" and self.id == 1)

    api = SafrsFastAPI(FastAPI(), prefix="/api")
    items = [_InstanceScopedModel(1, "hunter2"), _InstanceScopedModel(2, "decoy")]

    denied = api._apply_filter(
        _InstanceScopedModel,
        _request("/api/Account/", "filter[secret]=hunter2"),
        items,
    )
    allowed = api._apply_filter(
        _InstanceScopedModel,
        _request("/api/Account/", "filter[secret]=decoy"),
        items,
    )

    assert denied == []
    assert [item.id for item in allowed] == [2]


def test_error_response_docs_include_415_and_422() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    responses = api._jsonapi_error_responses()

    assert 415 in responses
    assert 422 in responses


def test_fastapi_post_upsert_uses_existing_update_path() -> None:
    updates: list[dict[str, Any]] = []

    class Existing:
        def _s_update_from_post(self, **params: Any) -> Existing:
            updates.append(params)
            return self

    existing = Existing()

    class UpsertModel:
        _s_type = "UpsertModel"

        @classmethod
        def _s_get_upsert_target(cls, jsonapi_id: Any, **_attrs: Any) -> Existing | None:
            return existing if jsonapi_id == "1" else None

        @classmethod
        def _s_post(cls, **_params: Any) -> Any:
            raise AssertionError("existing upserts must not call the create hook")

    api = SafrsFastAPI(FastAPI(), prefix="/api")
    result, created = api._create_post_object(
        UpsertModel,
        {
            "type": "UpsertModel",
            "id": "1",
            "attributes": {"name": "updated"},
            "relationships": {"owner": {"data": None}},
        },
    )

    assert result is existing
    assert created is False
    assert updates == [{"name": "updated", "owner": {"data": None}}]


def test_invalid_custom_filter_result_raises_validation_error() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")

    class _BadFilterModel:
        _s_jsonapi_attrs: dict[str, Any] = {}

        @staticmethod
        @jsonapi_filter_fields()
        def filter(_raw: str) -> dict[str, str]:
            return {"invalid": "result"}

    with pytest.raises(ValidationError):
        api._apply_filter(_BadFilterModel, _request("/api/Order/", "filter=bad"), [])


@pytest.mark.parametrize(
    "query, message",
    [
        ("filter[CategoryId]=not-an-integer", "Invalid filter value"),
        ("filter[CategoryId]=", "requires a value"),
        ("filter[CategoryId]junk=1", "Invalid bracket filter parameter"),
    ],
)
def test_fastapi_bracket_filter_rejects_invalid_values_and_names(query: str, message: str) -> None:
    class _IntegerAttribute:
        type = SimpleNamespace(python_type=int)

    class _TypedModel:
        CategoryId = _IntegerAttribute()
        _s_jsonapi_attrs = {"CategoryId": CategoryId}

    api = SafrsFastAPI(FastAPI(), prefix="/api")
    with pytest.raises(ValidationError) as exc:
        api._apply_filter(_TypedModel, _request("/api/Product/", query), [])
    assert message in exc.value.message


@pytest.mark.parametrize(
    "raw_filter",
    ["1", "[]", '[{"name":"CategoryId","op":"eq","val":1},null]'],
)
def test_fastapi_legacy_filter_errors_include_a_jsonapi_detail(raw_filter: str) -> None:
    class _FilterModel:
        _s_jsonapi_attrs = {"CategoryId": object()}

        @classmethod
        @jsonapi_filter_fields()
        def _s_filter(cls, raw: str) -> Any:
            from safrs.filtering import parse_filter_json

            parse_filter_json(raw)
            return []

    api = SafrsFastAPI(FastAPI(), prefix="/api")
    with pytest.raises(JSONAPIHTTPError) as exc:
        api._apply_filter(_FilterModel, _request("/api/Product/", f"filter={raw_filter}"), [])
    error = exc.value.payload["errors"][0]
    assert error["status"] == "400"
    assert error["title"] == "ValidationError"
    assert "expected a clause object" in error["detail"]


def test_get_collection_uses_model_s_get(monkeypatch: pytest.MonkeyPatch) -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    calls: dict[str, Any] = {}

    class _CollectionModel:
        _s_type = "Thing"
        _s_collection_name = "Thing"

        @classmethod
        def _s_get(cls) -> list[str]:
            context = maybe_jsonapi_context()
            calls["filter[name]"] = None if context is None else context.query_params.get("filter[name]")
            return ["shared-query"]

    monkeypatch.setattr(api, "_parse_include_paths", lambda Model, request: [])
    monkeypatch.setattr(api, "_authorize_collection_before_metadata", lambda Model, value, request: value)
    monkeypatch.setattr(api, "_apply_sort_query_or_items", lambda Model, value, request: value)
    monkeypatch.setattr(api, "_query_or_items_count", lambda value: len(value))
    monkeypatch.setattr(api, "_pagination_args", lambda request: (0, 250))
    monkeypatch.setattr(api, "_apply_pagination", lambda value, request: value)
    monkeypatch.setattr(api, "_coerce_items", lambda value: value)
    monkeypatch.setattr(api, "_pagination_links", lambda request, **kwargs: {})
    monkeypatch.setattr(api, "_jsonapi_data_response", lambda **kwargs: kwargs)

    handler = api._get_collection(_CollectionModel)
    response = handler(_request("/api/Thing/", "filter[name]=alpha"))

    assert calls["filter[name]"] == "alpha"
    assert response["data"] == ["shared-query"]


def test_patch_id_comparison_uses_validate_id_normalization() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    handler = api._patch_instance(_PatchModel)
    request = _request("/api/Thing/1", "")

    response = handler(
        "1",
        request,
        payload={"data": {"type": "Thing", "id": "01", "attributes": {}}},
    )
    assert response.status_code == 200

    with pytest.raises(JSONAPIHTTPError) as exc_info:
        handler(
            "1",
            request,
            payload={"data": {"type": "Thing", "id": "02", "attributes": {}}},
        )

    assert exc_info.value.status_code == 400
