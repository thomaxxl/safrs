from __future__ import annotations

from typing import Any, Iterable, List, Tuple

from safrs import SAFRSBase
from safrs.jsonapi_context import JsonApiContext, maybe_jsonapi_context, reset_jsonapi_context, set_jsonapi_context


class _QueryParams:
    def __init__(self, pairs: Iterable[Tuple[str, str]]) -> None:
        self._pairs: List[Tuple[str, str]] = [(str(key), str(value)) for key, value in pairs]

    def get(self, key: str, default: Any = None) -> Any:
        for item_key, item_value in self._pairs:
            if item_key == key:
                return item_value
        return default

    def items(self, multi: bool = False):  # type: ignore[override]
        if multi:
            return list(self._pairs)
        seen: dict[str, str] = {}
        for key, value in self._pairs:
            if key not in seen:
                seen[key] = value
        return list(seen.items())

    def multi_items(self) -> List[Tuple[str, str]]:
        return list(self._pairs)


class _Model:
    _s_collection_name = "Order"
    _s_type = "Order"
    _s_class_name = "Order"


class _Obj:
    jsonapi_id = "10248"


class _EncodeProbe:
    _s_collection_name = "Order"
    _s_type = "Order"
    jsonapi_id = "10248"

    def to_dict(self) -> dict[str, str]:
        return {"ShipName": "A"}

    def _s_get_related(self) -> dict[str, Any]:
        return {}

    @property
    def _s_url(self) -> str:
        raise AssertionError("_s_url should not be used when JsonApiContext is set")


def test_jsonapi_context_parses_jsonapi_params() -> None:
    params = _QueryParams(
        [
            ("include", "Customer,Employee"),
            ("exclude", "Orders"),
            ("fields[Order]", "Id,ShipName"),
            ("page[offset]", "10"),
            ("page[limit]", "5"),
            ("page[items][limit]", "2"),
        ]
    )
    ctx = JsonApiContext(query_params=params, prefix="/api")

    assert ctx.get_include_csv() == "Customer,Employee"
    assert ctx.get_exclude_csv() == "Orders"
    assert ctx.get_sparse_fields_map() == {"Order": ["Id", "ShipName"]}
    assert ctx.sparse_fields_for_model(_Model) == ["Id", "ShipName"]
    assert ctx.get_page_offset() == 10
    assert ctx.get_page_limit() == 5
    assert ctx.get_relationship_page_limit("items") == 2


def test_jsonapi_context_builds_paths_and_tracks_contextvar() -> None:
    ctx = JsonApiContext(query_params=_QueryParams([]), prefix="/api")

    assert ctx.collection_path(_Model) == "/api/Order/"
    assert ctx.instance_path(_Model, _Obj()) == "/api/Order/10248/"
    assert ctx.relationship_path(_Model, _Obj(), "Customer") == "/api/Order/10248/Customer"

    token = set_jsonapi_context(ctx)
    assert maybe_jsonapi_context() is ctx
    reset_jsonapi_context(token)
    assert maybe_jsonapi_context() is None


def test_jsonapi_context_reset_is_safe_when_token_is_reused() -> None:
    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([])))
    reset_jsonapi_context(token)
    # Resetting with the same token twice should not raise in cross-context cleanup paths.
    reset_jsonapi_context(token)
    assert maybe_jsonapi_context() is None


def test_jsonapi_encode_uses_context_instance_path_without_url_for() -> None:
    token = set_jsonapi_context(JsonApiContext(query_params=_QueryParams([]), prefix="/api"))
    try:
        payload = SAFRSBase._s_jsonapi_encode.__func__(_EncodeProbe())
    finally:
        reset_jsonapi_context(token)

    assert payload["links"]["self"] == "/api/Order/10248/"
