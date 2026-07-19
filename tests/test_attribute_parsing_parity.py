import datetime
from typing import Any, Callable

import pytest
import sqlalchemy
from flask import Flask

from safrs import SAFRSBase, jsonapi_attr
from safrs.errors import ValidationError
from safrs.jsonapi_context import (
    JsonApiContext,
    reset_jsonapi_context,
    set_jsonapi_context,
)


class _AttributeParityModel(SAFRSBase):
    @jsonapi_attr(
        parser=int,
        validator=lambda value: value >= 0,
        swagger_type="integer",
    )
    def parsed_count(self) -> int:
        return getattr(self, "_parsed_count", 0)

    @parsed_count.setter
    def parsed_count(self, value: int) -> None:
        object.__setattr__(self, "_parsed_count", value)

    @jsonapi_attr
    def readonly_label(self) -> str:
        return "read-only"


_AttributeParityModel._s_jsonapi_attrs = {
    "some_date": sqlalchemy.Column("some_date", sqlalchemy.Date),
    "some_datetime": sqlalchemy.Column("some_datetime", sqlalchemy.DateTime),
    "some_time": sqlalchemy.Column("some_time", sqlalchemy.Time),
    "parsed_count": _AttributeParityModel.parsed_count,
    "readonly_label": _AttributeParityModel.readonly_label,
}


def _instance() -> _AttributeParityModel:
    return object.__new__(_AttributeParityModel)


def _parse_in_flask(
    instance: _AttributeParityModel,
    attr_name: str,
    value: Any,
) -> Any:
    app = Flask("attribute-parity")
    with app.test_request_context("/"):
        return instance._s_parse_attr_value(attr_name, value)


def _parse_in_fastapi_context(
    instance: _AttributeParityModel,
    attr_name: str,
    value: Any,
) -> Any:
    token = set_jsonapi_context(JsonApiContext(query_params={}))
    try:
        return instance._s_parse_attr_value(attr_name, value)
    finally:
        reset_jsonapi_context(token)


@pytest.mark.parametrize(
    ("attr_name", "value", "expected"),
    [
        ("some_date", "2024-02-29", datetime.datetime(2024, 2, 29)),
        (
            "some_datetime",
            "2024-02-29 01:02:03.456789",
            datetime.datetime(2024, 2, 29, 1, 2, 3, 456789),
        ),
        ("some_time", "01:02:03.456789", datetime.time(1, 2, 3, 456789)),
        ("parsed_count", "7", 7),
    ],
)
def test_flask_and_fastapi_contexts_use_identical_reference_parsing(
    attr_name: str,
    value: Any,
    expected: Any,
) -> None:
    instance = _instance()

    assert _parse_in_flask(instance, attr_name, value) == expected
    assert _parse_in_fastapi_context(instance, attr_name, value) == expected


@pytest.mark.parametrize(
    ("attr_name", "value"),
    [
        ("some_date", "not-a-date"),
        ("some_datetime", "2024-02-29T01:02:03"),
        ("some_time", "not-a-time"),
        ("parsed_count", "-1"),
        ("readonly_label", "override"),
    ],
)
def test_flask_and_fastapi_contexts_reject_values_identically(
    attr_name: str,
    value: Any,
) -> None:
    instance = _instance()
    parsers: tuple[Callable[[_AttributeParityModel, str, Any], Any], ...] = (
        _parse_in_flask,
        _parse_in_fastapi_context,
    )
    messages = []

    for parser in parsers:
        with pytest.raises(ValidationError) as exc_info:
            parser(instance, attr_name, value)
        messages.append(exc_info.value.message)

    assert messages[0] == messages[1]


def test_programmatic_model_values_remain_unparsed_without_request_context() -> None:
    raw_value = "2024-02-29"

    assert _instance()._s_parse_attr_value("some_date", raw_value) == raw_value
