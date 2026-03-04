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
from safrs.fastapi.api import JSONAPIHTTPError, SafrsFastAPI, install_jsonapi_exception_handlers


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
    _s_jsonapi_attrs = {"CustomerId": object(), "OrderDate": object(), "id": object()}
    id = object()
    CategoryId = object()

    class id_type:
        primary_keys = ["id"]

        @staticmethod
        def validate_id(value: Any) -> int:
            return int(value)


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


def test_error_response_docs_include_415_and_422() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")
    responses = api._jsonapi_error_responses()

    assert 415 in responses
    assert 422 in responses


def test_invalid_custom_filter_result_raises_validation_error() -> None:
    api = SafrsFastAPI(FastAPI(), prefix="/api")

    class _BadFilterModel:
        _s_jsonapi_attrs: dict[str, Any] = {}

        @staticmethod
        def filter(_raw: str) -> dict[str, str]:
            return {"invalid": "result"}

    with pytest.raises(ValidationError):
        api._apply_filter(_BadFilterModel, _request("/api/Order/", "filter=bad"), [])


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
