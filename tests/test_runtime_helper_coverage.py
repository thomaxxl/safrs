import decimal
import logging
from types import SimpleNamespace
from typing import Any

import pytest

import safrs
from safrs import errors, jsonapi_context
from safrs.fastapi.schemas import examples, from_sqlalchemy


def test_error_request_url_and_resource_inference_edge_cases(monkeypatch):
    token = errors.set_fastapi_request_url(None)
    try:
        monkeypatch.setattr(errors, "has_request_context", lambda: False)
        assert errors._current_request_url() is None
    finally:
        errors.reset_fastapi_request_url(token)

    class BrokenRequest:
        @property
        def url(self):
            raise RuntimeError("unavailable")

    monkeypatch.setattr(errors, "has_request_context", lambda: True)
    monkeypatch.setattr(errors, "request", BrokenRequest())
    assert errors._current_request_url() is None

    class BrokenUrl:
        def __str__(self):
            raise RuntimeError("invalid")

    assert errors._infer_resource_and_object_id(None) == (None, None)
    assert errors._infer_resource_and_object_id(BrokenUrl()) == (None, None)
    assert errors._infer_resource_and_object_id("https://example.test/") == (None, None)
    assert errors._infer_resource_and_object_id("https://example.test/root/api") == (None, None)


def test_integrity_logging_can_exit_without_inspecting_exception(monkeypatch):
    class ExplosiveException:
        def __getattribute__(self, name):
            if name in {"orig", "statement", "params"}:
                raise AssertionError(name)
            return super().__getattribute__(name)

    monkeypatch.setattr(safrs.log, "isEnabledFor", lambda level: level != logging.DEBUG)
    errors.log_integrity_error_details(ExplosiveException())


def test_user_facing_error_classes_cover_debug_and_hidden_messages(monkeypatch):
    monkeypatch.setattr(errors.NotFoundError, "message", "NotFoundError ")
    monkeypatch.setattr(errors, "is_debug", lambda: False)
    not_found = errors.NotFoundError("secret")
    assert errors.HIDDEN_LOG in not_found.message

    monkeypatch.setattr(errors.UnAuthorizedError, "message", "Authorization Error: ")
    hidden_auth = errors.UnAuthorizedError("secret", status_code=401)
    assert hidden_auth.status_code == 401
    assert errors.HIDDEN_LOG in hidden_auth.message

    monkeypatch.setattr(errors.UnAuthorizedError, "message", "Authorization Error: ")
    monkeypatch.setattr(errors, "is_debug", lambda: True)
    visible_auth = errors.UnAuthorizedError("visible")
    assert "visible" in visible_auth.message

    monkeypatch.setattr(errors.GenericError, "message", "Generic Error: ")
    monkeypatch.setattr(errors, "_current_request_url", lambda: None)
    visible_generic = errors.GenericError("details")
    assert "details" in visible_generic.message

    monkeypatch.setattr(errors.GenericError, "message", "Generic Error: ")
    monkeypatch.setattr(errors, "is_debug", lambda: False)
    hidden_generic = errors.GenericError("secret")
    assert errors.HIDDEN_LOG in hidden_generic.message

    monkeypatch.setattr(errors.IntegerOverflowError, "message", "Integer Overflow Error: ")
    overflow = errors.IntegerOverflowError("too large", status_code=422)
    assert overflow.status_code == 422
    assert overflow.message.endswith("too large")


def test_jsonapi_context_low_level_defaults_and_sparse_candidates():
    assert jsonapi_context._normalize_prefix(" api/v1/ ") == "/api/v1"
    assert jsonapi_context._multi_items(object()) == []
    assert jsonapi_context._get_param(object(), "missing", "fallback") == "fallback"

    context = jsonapi_context.JsonApiContext({"fields[Known]": "name"})
    anonymous_model = SimpleNamespace(_s_class_name="", _s_type="", __name__="")
    assert context.sparse_fields_for_model(anonymous_model) is None


def test_jsonapi_context_numbered_pagination_and_relationship_bounds(monkeypatch):
    values = {"DEFAULT_PAGE_LIMIT": 5, "MAX_PAGE_LIMIT": 10}
    monkeypatch.setattr(jsonapi_context, "get_config", values.get)

    numbered = jsonapi_context.JsonApiContext(
        {"page[number]": "3", "page[size]": "4"}
    )
    assert numbered.get_page_offset() == 8
    assert numbered.get_page_limit() == 4

    relationship = jsonapi_context.JsonApiContext(
        {
            "page[children][number]": "2",
            "page[children][size]": "7",
        }
    )
    assert relationship.get_relationship_page_limit("children") == 7
    assert (
        jsonapi_context.JsonApiContext(
            {"page[children][limit]": "-1"}
        ).get_relationship_page_limit("children")
        == 1
    )
    assert (
        jsonapi_context.JsonApiContext(
            {"page[children][limit]": "99"}
        ).get_relationship_page_limit("children")
        == 10
    )


def test_jsonapi_context_prefixed_path_and_required_accessor():
    model = SimpleNamespace(__name__="Entry", _s_collection_name="entries")
    context = jsonapi_context.JsonApiContext({}, prefix="api/v1/")
    assert context.collection_path(model) == "/api/v1/entries/"

    token = jsonapi_context._CURRENT_JSONAPI_CONTEXT.set(None)
    try:
        with pytest.raises(RuntimeError, match="context is not set"):
            jsonapi_context.get_jsonapi_context()
    finally:
        jsonapi_context._CURRENT_JSONAPI_CONTEXT.reset(token)


def test_sqlalchemy_schema_type_helpers_cover_dynamic_attributes():
    assert from_sqlalchemy._safe_python_type(object()) is Any

    class NotImplementedType:
        @property
        def python_type(self):
            raise NotImplementedError

    class BrokenType:
        @property
        def python_type(self):
            raise RuntimeError("dynamic")

    assert from_sqlalchemy._safe_python_type(SimpleNamespace(type=NotImplementedType())) is Any
    assert from_sqlalchemy._safe_python_type(SimpleNamespace(type=BrokenType())) is Any
    assert from_sqlalchemy._safe_python_type(
        SimpleNamespace(type=SimpleNamespace(python_type=None))
    ) is Any

    decimal_attr = SimpleNamespace(__annotations__={"return": decimal.Decimal})
    decimal_model = type("DecimalModel", (), {"amount": decimal_attr})
    assert from_sqlalchemy._jsonapi_attr_return_type(decimal_model, "amount") is float

    string_attr = SimpleNamespace(
        __annotations__={"return": "ForwardReference"},
        swagger_type="boolean",
    )
    string_model = type("StringModel", (), {"enabled": string_attr})
    assert from_sqlalchemy._jsonapi_attr_return_type(string_model, "enabled") is bool


def test_sqlalchemy_schema_field_and_sample_fallbacks(monkeypatch):
    monkeypatch.setattr(from_sqlalchemy, "is_jsonapi_attr", lambda attr: True)
    monkeypatch.setattr(from_sqlalchemy, "jsonapi_attr_is_read_only", lambda attr: False)
    monkeypatch.setattr(from_sqlalchemy, "jsonapi_attr_is_write_only", lambda attr: False)

    field = from_sqlalchemy._attribute_field_info(
        SimpleNamespace(default="sample", description="A sample")
    )
    assert field.default == "sample"
    assert field.description == "A sample"

    assert from_sqlalchemy._sample_example(type("NoFactory", (), {})) is None

    class BrokenFactory:
        @staticmethod
        def _s_sample_dict():
            raise RuntimeError("unavailable")

    class NonDictFactory:
        @staticmethod
        def _s_sample_dict():
            return ["not", "a", "dict"]

    assert from_sqlalchemy._sample_example(BrokenFactory) is None
    assert from_sqlalchemy._sample_example(NonDictFactory) is None


def test_document_examples_filter_directional_attributes_and_tolerate_factories(monkeypatch):
    normal = SimpleNamespace(kind="normal")
    read_only = SimpleNamespace(kind="read")
    write_only = SimpleNamespace(kind="write")
    model = type(
        "ExampleModel",
        (),
        {
            "_s_type": "examples",
            "_s_jsonapi_attrs": {
                "normal": normal,
                "read_only": read_only,
                "write_only": write_only,
            },
            "_s_sample_dict": staticmethod(
                lambda: {"normal": 1, "read_only": 2, "write_only": 3}
            ),
        },
    )
    monkeypatch.setattr(examples, "is_jsonapi_attr", lambda attr: attr is not normal)
    monkeypatch.setattr(
        examples, "jsonapi_attr_is_read_only", lambda attr: attr is read_only
    )
    monkeypatch.setattr(
        examples, "jsonapi_attr_is_write_only", lambda attr: attr is write_only
    )

    assert examples.attributes_example(model) == {"normal": 1, "read_only": 2}
    assert examples.attributes_example(model, writable_only=True) == {
        "normal": 1,
        "write_only": 3,
    }

    class BrokenFactories:
        @staticmethod
        def _s_sample_dict():
            raise RuntimeError("unavailable")

        @staticmethod
        def _s_sample_id():
            raise RuntimeError("unavailable")

    assert examples.attributes_example(BrokenFactories) == {}
    assert examples.resource_identifier_example(BrokenFactories)["id"] == "0"
