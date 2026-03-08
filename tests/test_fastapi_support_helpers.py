from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI

from safrs.fastapi.api import SafrsFastAPI
from safrs.fastapi.relationships import relationship_is_exposed
from safrs.fastapi.schemas.examples import attributes_example, resource_identifier_example


def test_example_builders_fallback_when_sample_factories_raise() -> None:
    class _BrokenModel:
        _s_type = "Broken"

        @staticmethod
        def _s_sample_dict() -> dict[str, Any]:
            raise RuntimeError("broken sample")

        @staticmethod
        def _s_sample_id() -> str:
            raise RuntimeError("broken sample id")

    assert attributes_example(_BrokenModel) == {}
    assert resource_identifier_example(_BrokenModel) == {"type": "Broken", "id": "0"}


def test_relationship_is_exposed_handles_mapper_and_instance_lookup_errors() -> None:
    class _BrokenRelationships:
        @staticmethod
        def get(_name: str) -> Any:
            raise RuntimeError("broken relationships mapping")

    class _BrokenMapper:
        relationships = _BrokenRelationships()

    class _RaisesOnClassGet:
        def __get__(self, _instance: Any, _owner: Any) -> Any:
            raise RuntimeError("broken class attr")

    class _BrokenModel:
        __mapper__ = _BrokenMapper()
        bad_rel = _RaisesOnClassGet()

    rel_prop = SimpleNamespace(expose=True)
    assert relationship_is_exposed(_BrokenModel, "bad_rel", rel_prop) is True


def test_apply_sort_to_list_falls_back_when_values_are_not_orderable() -> None:
    class _SortModel:
        _s_jsonapi_attrs = {"CustomerId": object()}
        id = object()

    api = SafrsFastAPI(FastAPI(), prefix="/api")
    items = [
        SimpleNamespace(id=1, CustomerId={"a": 1}),
        SimpleNamespace(id=2, CustomerId=5),
    ]

    result = api._apply_sort_to_list(_SortModel, items, [("CustomerId", False)])
    assert [item.id for item in result] == [1, 2]

