from __future__ import annotations

import datetime
from typing import Any

import pytest
import yaml

from safrs import api_doc
from safrs.errors import SystemValidationError
from safrs.jabase import JABase


def test_jabase_default_lifecycle_and_metadata() -> None:
    class StatelessResource(JABase):
        instances: list[Any] = []

    resource = StatelessResource(id="resource-1")

    assert StatelessResource.instances == [resource]
    assert resource.id == "resource-1"
    assert resource.jsonapi_id == "resource-1"
    assert StatelessResource.s_type == "JAType_StatelessResource"
    assert StatelessResource.get() == {}
    assert resource.patch() == {}
    assert resource.delete() is None
    assert StatelessResource._s_count() == 0


def test_parse_object_doc_maps_yaml_scanner_errors_to_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scanner_error = yaml.scanner.ScannerError(
        "while scanning documentation",
        None,
        "invalid YAML",
        None,
    )
    monkeypatch.setattr(
        api_doc.yaml,
        "safe_load",
        lambda _raw_doc: (_ for _ in ()).throw(scanner_error),
    )

    def documented_method() -> None:
        """description: broken"""

    assert api_doc.parse_object_doc(documented_method) == {"description": "description: broken"}


def test_parse_object_doc_wraps_unexpected_yaml_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unexpected_error = RuntimeError("loader failed")
    monkeypatch.setattr(
        api_doc.yaml,
        "safe_load",
        lambda _raw_doc: (_ for _ in ()).throw(unexpected_error),
    )

    def documented_method() -> None:
        """description: unavailable"""

    with pytest.raises(SystemValidationError) as exc_info:
        api_doc.parse_object_doc(documented_method)

    assert exc_info.value.__cause__ is unexpected_error


def test_jsonapi_rpc_uses_post_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_doc, "get_config", lambda _key: True)

    @api_doc.jsonapi_rpc()
    def documented_method() -> None:
        """description: default method"""

    assert api_doc.is_public(documented_method) is True
    assert api_doc.get_http_methods(documented_method) == ["POST"]
    assert api_doc.get_doc(documented_method) == {"description": "default method"}


def test_jsonapi_rpc_recovers_when_doc_parser_raises_scanner_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scanner_error = yaml.scanner.ScannerError(
        "while scanning documentation",
        None,
        "invalid YAML",
        None,
    )
    monkeypatch.setattr(api_doc, "get_config", lambda _key: True)
    monkeypatch.setattr(
        api_doc,
        "parse_object_doc",
        lambda _method: (_ for _ in ()).throw(scanner_error),
    )

    @api_doc.jsonapi_rpc(http_methods=["GET"])
    def documented_method() -> None:
        """description: broken"""

    assert api_doc.get_doc(documented_method) == {}
    assert api_doc.get_http_methods(documented_method) == ["GET"]


def test_resolve_rpc_method_rejects_unknown_method() -> None:
    class RpcResource:
        pass

    with pytest.raises(SystemValidationError) as exc_info:
        api_doc.resolve_rpc_method(RpcResource, "missing")

    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, {"type": "boolean", "example": True}),
        (3, {"type": "integer", "example": 3}),
        (1.5, {"type": "number", "example": 1.5}),
        (
            datetime.datetime(2024, 2, 29, 1, 2, 3),
            {"type": "string", "format": "date-time", "example": "2024-02-29 01:02:03"},
        ),
        (
            datetime.date(2024, 2, 29),
            {"type": "string", "format": "date", "example": "2024-02-29"},
        ),
        (datetime.time(1, 2, 3), {"type": "string", "example": "01:02:03"}),
        ({"key": "value"}, {"type": "object", "additionalProperties": True, "example": {"key": "value"}}),
        (["value"], {"type": "array", "items": {}, "example": ["value"]}),
        (None, {"type": "string", "example": ""}),
    ],
)
def test_schema_for_example_value_covers_supported_types(
    value: Any,
    expected: dict[str, Any],
) -> None:
    assert api_doc.schema_for_example_value(value) == expected
