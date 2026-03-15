from __future__ import annotations

from typing import Any

import pytest
from flask import Flask

from safrs import SAFRSBase, jsonapi_attr
from safrs.base import SAFRSBase as _RuntimeBase
from safrs.errors import ValidationError
from safrs.jsonapi_attr import (
    get_jsonapi_attrs,
    jsonapi_attr_is_read_only,
    jsonapi_attr_is_write_only,
    lookup_jsonapi_attr,
)


class _RuntimeJsonapiAttrModel(SAFRSBase):
    _s_type = "RuntimeJsonapiAttrThing"
    _s_collection_name = "RuntimeJsonapiAttrThings"
    _s_jsonapi_attrs: dict[str, Any]

    @jsonapi_attr
    def readonly_value(self) -> str:
        return f"summary:{getattr(self, 'name', '')}"

    @jsonapi_attr(read_only=True, description="Explicit read-only facade")
    def explicit_readonly(self) -> str:
        return "locked"

    @explicit_readonly.setter
    def explicit_readonly(self, value: str) -> None:
        object.__setattr__(self, "_explicit_readonly", value)

    @jsonapi_attr(parser=int, validator=lambda value: value >= 0, swagger_type="integer")
    def count(self) -> int:
        return getattr(self, "_count", 0)

    @count.setter
    def count(self, value: int) -> None:
        object.__setattr__(self, "_count", value)

    @jsonapi_attr(write_only=True, description="Secret facade")
    def password(self) -> str:
        return "********"

    @password.setter
    def password(self, value: str) -> None:
        object.__setattr__(self, "_password", value)

    @jsonapi_attr
    def strict(self) -> str:
        return getattr(self, "_strict", "")

    @strict.setter
    def strict(self, value: str) -> None:
        raise ValueError("bad strict value")


_RuntimeJsonapiAttrModel._s_jsonapi_attrs = {
    "readonly_value": _RuntimeJsonapiAttrModel.readonly_value,
    "explicit_readonly": _RuntimeJsonapiAttrModel.explicit_readonly,
    "count": _RuntimeJsonapiAttrModel.count,
    "password": _RuntimeJsonapiAttrModel.password,
    "strict": _RuntimeJsonapiAttrModel.strict,
}


class _JsonapiAttrMixin:
    @jsonapi_attr(description="Inherited attribute")
    def inherited(self) -> str:
        return "inherited"


class _InheritedJsonapiAttrModel(_JsonapiAttrMixin, SAFRSBase):
    _s_type = "InheritedJsonapiAttrThing"
    _s_collection_name = "InheritedJsonapiAttrThings"


def _instance() -> _RuntimeJsonapiAttrModel:
    instance = object.__new__(_RuntimeJsonapiAttrModel)
    object.__setattr__(instance, "name", "alpha")
    object.__setattr__(instance, "_count", 0)
    object.__setattr__(instance, "_password", "secret")
    return instance


def test_jsonapi_attr_kwargs_metadata_survives_setter_copy() -> None:
    class _KwargMetadataModel:
        @jsonapi_attr(description="Count", default=3, swagger_type="integer", write_only=True)
        def count(self) -> int:
            return 3

        @count.setter
        def count(self, value: int) -> None:
            self._count = value

    attr = _KwargMetadataModel.count

    assert attr.description == "Count"
    assert attr.default == 3
    assert attr.swagger_type == "integer"
    assert jsonapi_attr_is_write_only(attr) is True


def test_direct_assignment_to_readonly_jsonapi_attr_raises() -> None:
    instance = _instance()

    with pytest.raises(AttributeError, match="Attribute 'readonly_value' is read-only"):
        instance.readonly_value = "nope"

    with pytest.raises(AttributeError, match="Attribute 'explicit_readonly' is read-only"):
        instance.explicit_readonly = "nope"


def test_parse_attr_rejects_readonly_and_applies_parser_validator() -> None:
    app = Flask(__name__)
    instance = _instance()

    with app.test_request_context("/"):
        with pytest.raises(ValidationError) as exc_info:
            instance._s_parse_attr_value("readonly_value", "changed")
        assert exc_info.value.message.endswith("Attribute 'readonly_value' is read-only")

        with pytest.raises(ValidationError) as exc_info:
            instance._s_parse_attr_value("explicit_readonly", "changed")
        assert exc_info.value.message.endswith("Attribute 'explicit_readonly' is read-only")

        assert instance._s_parse_attr_value("count", "7") == 7

        with pytest.raises(ValidationError) as exc_info:
            instance._s_parse_attr_value("count", "-1")
        assert exc_info.value.message.endswith("Invalid value for attribute 'count'")


def test_set_jsonapi_attr_maps_type_and_value_errors_to_validation_error() -> None:
    instance = _instance()

    with pytest.raises(ValidationError) as exc_info:
        instance._s_set_jsonapi_attr("strict", "boom")
    assert exc_info.value.message.endswith("bad strict value")


def test_ignore_unchanged_readonly_jsonapi_attr_requires_exact_match() -> None:
    instance = _instance()

    assert instance._s_ignore_unchanged_readonly_jsonapi_attr("readonly_value", "summary:alpha") is True
    assert instance._s_ignore_unchanged_readonly_jsonapi_attr("readonly_value", "summary:beta") is False
    assert instance._s_ignore_unchanged_readonly_jsonapi_attr("count", 0) is False


def test_lookup_and_collection_include_inherited_jsonapi_attrs() -> None:
    inherited = lookup_jsonapi_attr(_InheritedJsonapiAttrModel, "inherited")
    attrs = get_jsonapi_attrs(_InheritedJsonapiAttrModel)

    assert inherited is attrs["inherited"]
    assert inherited.fget.__name__ == "inherited"
    assert inherited.description == "Inherited attribute"


def test_runtime_response_serialization_skips_write_only_jsonapi_attrs() -> None:
    instance = _instance()
    serialized = _RuntimeBase.__dict__["_s_jsonapi_attrs"].fget(instance)

    assert serialized["readonly_value"] == "summary:alpha"
    assert "password" not in serialized


def test_jsonapi_attr_read_only_and_write_only_helpers_reflect_metadata() -> None:
    assert jsonapi_attr_is_read_only(_RuntimeJsonapiAttrModel.readonly_value) is True
    assert jsonapi_attr_is_read_only(_RuntimeJsonapiAttrModel.explicit_readonly) is True
    assert jsonapi_attr_is_write_only(_RuntimeJsonapiAttrModel.password) is True
