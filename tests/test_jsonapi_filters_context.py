from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from flask import Flask
import pytest

from safrs import jsonapi_filters
from safrs.errors import ValidationError
from safrs.jsonapi_context import JsonApiContext, reset_jsonapi_context, set_jsonapi_context
from safrs.filtering import jsonapi_filter_fields
from safrs.jsonapi_formatting import jsonapi_filter_list, jsonapi_filter_query
from safrs.request import SAFRSRequest


class _QueryParams:
    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = list(items)

    def get(self, key: str, default: Any = None) -> Any:
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        return default

    def multi_items(self) -> list[tuple[str, str]]:
        return list(self._items)


class _FakeLoad:
    def __init__(self, path: str) -> None:
        self.path = path

    def joinedload(self, rel: Any) -> "_FakeLoad":
        return _FakeLoad(f"{self.path}.{rel.key}")


class _FakeQuery:
    def __init__(self) -> None:
        self.options_calls: list[str] = []
        self.filter_calls: list[Any] = []

    def options(self, option: _FakeLoad) -> "_FakeQuery":
        self.options_calls.append(option.path)
        return self

    def filter(self, *expressions: Any) -> "_FakeQuery":
        self.filter_calls.extend(expressions)
        return self


class _FakeColumn:
    def __init__(self, name: str, *, filterable: bool = True) -> None:
        self.name = name
        self.filterable = filterable

    def in_(self, values: list[str]) -> tuple[str, tuple[str, ...]]:
        return (self.name, tuple(values))


class _Rel:
    def __init__(self, key: str, target: Any, lazy: str = "select") -> None:
        self.key = key
        self.lazy = lazy
        self.mapper = SimpleNamespace(class_=target)


def test_create_query_uses_jsonapi_context_include_star_and_explicit_paths(
    monkeypatch: Any,
) -> None:
    query = _FakeQuery()

    class _ReviewModel:
        _s_relationships: dict[str, Any] = {}

    reviews_rel = _Rel("Reviews", _ReviewModel)

    class _ProductModel:
        _s_relationships = {"Reviews": reviews_rel}
        Reviews = reviews_rel

    products_rel = _Rel("Products", _ProductModel)
    suppliers_rel = _Rel("Suppliers", _ReviewModel)

    class _CategoryModel:
        _s_query = query
        _s_relationships = {
            "Products": products_rel,
            "Suppliers": suppliers_rel,
        }
        Products = products_rel
        Suppliers = suppliers_rel

    monkeypatch.setattr(jsonapi_filters, "joinedload", lambda rel: _FakeLoad(rel.key))
    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("include", "+all,Products.Reviews")])))
    try:
        result = jsonapi_filters.create_query(_CategoryModel)
    finally:
        reset_jsonapi_context(token)

    assert result is query
    assert query.options_calls == ["Products", "Suppliers", "Products.Reviews"]


def test_jsonapi_filter_uses_jsonapi_context_bracket_filters() -> None:
    query = _FakeQuery()
    name_column = _FakeColumn("name")

    class _FilterModel:
        _s_query = query
        _s_relationships: dict[str, Any] = {}
        _s_jsonapi_attrs = {"name": name_column}

    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter[name]", "alpha,beta")])))
    try:
        result = jsonapi_filters.jsonapi_filter.__func__(_FilterModel)
    finally:
        reset_jsonapi_context(token)

    assert result is query
    assert query.filter_calls == [("name", ("alpha", "beta"))]


def test_jsonapi_filter_uses_jsonapi_context_custom_filter() -> None:
    class _FilterModel:
        _s_relationships: dict[str, Any] = {}
        _s_jsonapi_attrs: dict[str, Any] = {}
        called_with = ""

        @staticmethod
        @jsonapi_filter_fields()
        def filter(raw: str) -> list[str]:
            _FilterModel.called_with = raw
            return ["custom"]

    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter", "name=alpha")])))
    try:
        result = jsonapi_filters.jsonapi_filter.__func__(_FilterModel)
    finally:
        reset_jsonapi_context(token)

    assert result == ["custom"]
    assert _FilterModel.called_with == "name=alpha"


def test_jsonapi_filter_preserves_flask_request_behavior() -> None:
    app = Flask(__name__)
    app.request_class = SAFRSRequest
    query = _FakeQuery()
    name_column = _FakeColumn("name")

    class _FilterModel:
        _s_query = query
        _s_relationships: dict[str, Any] = {}
        _s_jsonapi_attrs = {"name": name_column}

    with app.test_request_context("/?filter[name]=alpha"):
        result = jsonapi_filters.jsonapi_filter.__func__(_FilterModel)

    assert result is query
    assert query.filter_calls == [("name", ("alpha",))]


def test_jsonapi_filter_prefers_jsonapi_context_when_flask_request_has_no_filter_args() -> None:
    app = Flask(__name__)
    app.request_class = SAFRSRequest
    query = _FakeQuery()
    name_column = _FakeColumn("name")

    class _FilterModel:
        _s_query = query
        _s_relationships: dict[str, Any] = {}
        _s_jsonapi_attrs = {"name": name_column}

    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter[name]", "beta")])))
    try:
        with app.test_request_context("/"):
            result = jsonapi_filters.jsonapi_filter.__func__(_FilterModel)
    finally:
        reset_jsonapi_context(token)

    assert result is query
    assert query.filter_calls == [("name", ("beta",))]


def test_jsonapi_filter_enforces_filterable_column_flag() -> None:
    query = _FakeQuery()
    internal_column = _FakeColumn("internal", filterable=False)

    class _FilterModel:
        _s_query = query
        _s_relationships: dict[str, Any] = {}
        _s_jsonapi_attrs = {"internal": internal_column}

    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter[internal]", "value")])))
    try:
        with pytest.raises(ValidationError) as exc:
            jsonapi_filters.jsonapi_filter.__func__(_FilterModel)
    finally:
        reset_jsonapi_context(token)

    assert "unknown attribute" in exc.value.message
    assert query.filter_calls == []


def test_jsonapi_context_rejects_malformed_bracket_filter_name() -> None:
    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter[name]junk", "value")])))
    try:
        with pytest.raises(ValidationError) as exc:
            jsonapi_filters._get_bracket_filters()
    finally:
        reset_jsonapi_context(token)
    assert "Invalid bracket filter parameter" in exc.value.message


def test_flask_custom_filter_rejects_invalid_result_shape() -> None:
    class _FilterModel:
        _s_jsonapi_attrs: dict[str, Any] = {}

        @staticmethod
        @jsonapi_filter_fields()
        def filter(_raw: str) -> dict[str, str]:
            return {"invalid": "result"}

    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([("filter", "custom")])))
    try:
        with pytest.raises(ValidationError) as exc:
            jsonapi_filters.jsonapi_filter.__func__(_FilterModel)
    finally:
        reset_jsonapi_context(token)
    assert "Invalid filter result" in exc.value.message


def test_relationship_filtering_accepts_permission_filtered_lists() -> None:
    class _Item:
        allowed: list[Any] = []
        id_type = object()

        @classmethod
        def jsonapi_filter(cls) -> list[Any]:
            return cls.allowed

    denied = _Item()
    allowed = _Item()
    _Item.allowed = [allowed]

    class _RelationshipQuery:
        @staticmethod
        def all() -> list[Any]:
            return [denied, allowed]

    assert set(jsonapi_filter_list(["raw", denied, allowed])) == {"raw", allowed}
    assert jsonapi_filter_query(_RelationshipQuery(), _Item) == [allowed]
