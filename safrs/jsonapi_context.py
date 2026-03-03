from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import safrs
from .config import get_config


def _normalize_prefix(prefix: str) -> str:
    trimmed = str(prefix or "").strip()
    if not trimmed:
        return ""
    if not trimmed.startswith("/"):
        trimmed = "/" + trimmed
    return trimmed.rstrip("/")


def _multi_items(query_params: Any) -> List[Tuple[str, str]]:
    if hasattr(query_params, "multi_items") and callable(query_params.multi_items):
        return [(str(key), str(value)) for key, value in query_params.multi_items()]

    items_method = getattr(query_params, "items", None)
    if callable(items_method):
        try:
            # Flask MultiDict supports items(multi=True).
            return [(str(key), str(value)) for key, value in items_method(multi=True)]
        except TypeError:
            return [(str(key), str(value)) for key, value in items_method()]

    return []


def _get_param(query_params: Any, key: str, default: Optional[str] = None) -> Optional[str]:
    getter = getattr(query_params, "get", None)
    if callable(getter):
        value = getter(key, default)
        if value is None:
            return None
        return str(value)
    return default


def _parse_int(raw: Optional[str], default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class JsonApiContext:
    query_params: Any
    prefix: str = ""
    ja_data: set[Any] = field(default_factory=set)
    ja_included: set[Any] = field(default_factory=set)
    collection_path_builder: Optional[Callable[[Any], str]] = None
    instance_path_builder: Optional[Callable[[Any, Any], str]] = None
    relationship_path_builder: Optional[Callable[[Any, Any, str], str]] = None

    def get_include_csv(self, default: str = "") -> str:
        value = _get_param(self.query_params, "include", default)
        return str(value or default)

    def get_exclude_csv(self, default: str = "") -> str:
        value = _get_param(self.query_params, "exclude", default)
        return str(value or default)

    def get_sparse_fields_map(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for key, value in _multi_items(self.query_params):
            if not key.startswith("fields[") or not key.endswith("]"):
                continue
            model_name = key[len("fields[") : -1]
            field_names = [field_name.strip() for field_name in str(value).split(",") if field_name.strip()]
            if field_names:
                result[model_name] = field_names
        return result

    def sparse_fields_for_model(self, Model: Any) -> Optional[List[str]]:
        fields_by_model = self.get_sparse_fields_map()
        candidates = [
            str(getattr(Model, "_s_class_name", "")),
            str(getattr(Model, "_s_type", "")),
            str(getattr(Model, "__name__", "")),
        ]
        for name in candidates:
            if not name:
                continue
            values = fields_by_model.get(name)
            if values:
                return values
        return None

    def get_page_offset(self) -> int:
        default_offset = 0
        offset = _parse_int(_get_param(self.query_params, "page[offset]"), default_offset)
        if offset == default_offset:
            page_number = _parse_int(_get_param(self.query_params, "page[number]"), 1)
            page_size = _parse_int(_get_param(self.query_params, "page[size]"), 0)
            if page_number > 0 and page_size > 0:
                offset = max(0, (page_number - 1) * page_size)
        max_page_offset = int(get_config("MAX_PAGE_OFFSET") or safrs.SAFRS.MAX_PAGE_OFFSET)
        if offset < 0:
            return 0
        if offset > max_page_offset:
            return max_page_offset
        return offset

    def get_page_limit(self) -> int:
        default_limit = int(get_config("DEFAULT_PAGE_LIMIT") or safrs.SAFRS.DEFAULT_PAGE_LIMIT)
        limit = _parse_int(_get_param(self.query_params, "page[limit]"), default_limit)
        if _get_param(self.query_params, "page[number]") is not None:
            size = _parse_int(_get_param(self.query_params, "page[size]"), limit)
            if size > 0:
                limit = size
        max_page_limit = int(get_config("MAX_PAGE_LIMIT") or safrs.SAFRS.MAX_PAGE_LIMIT)
        if limit <= 0:
            return 1
        if limit > max_page_limit:
            return max_page_limit
        return limit

    def get_relationship_page_limit(self, rel_name: str) -> int:
        key_limit = f"page[{rel_name}][limit]"
        key_size = f"page[{rel_name}][size]"
        key_number = f"page[{rel_name}][number]"

        base_limit = self.get_page_limit()
        limit = _parse_int(_get_param(self.query_params, key_limit), base_limit)
        if _get_param(self.query_params, key_number) is not None:
            size = _parse_int(_get_param(self.query_params, key_size), limit)
            if size > 0:
                limit = size

        max_page_limit = int(get_config("MAX_PAGE_LIMIT") or safrs.SAFRS.MAX_PAGE_LIMIT)
        if limit <= 0:
            return 1
        if limit > max_page_limit:
            return max_page_limit
        return limit

    def query_multi_items(self) -> List[Tuple[str, str]]:
        return _multi_items(self.query_params)

    def collection_path(self, Model: Any) -> str:
        if self.collection_path_builder is not None:
            return str(self.collection_path_builder(Model))
        collection_name = str(getattr(Model, "_s_collection_name", getattr(Model, "_s_type", Model.__name__))).strip("/")
        prefix = _normalize_prefix(self.prefix)
        if prefix:
            return f"{prefix}/{collection_name}/"
        return f"/{collection_name}/"

    def instance_path(self, Model: Any, obj: Any) -> str:
        if self.instance_path_builder is not None:
            return str(self.instance_path_builder(Model, obj))
        encoded_id = quote(str(obj.jsonapi_id), safe="")
        return f"{self.collection_path(Model)}{encoded_id}/"

    def relationship_path(self, Model: Any, obj: Any, rel_name: str) -> str:
        if self.relationship_path_builder is not None:
            return str(self.relationship_path_builder(Model, obj, rel_name))
        base = self.instance_path(Model, obj)
        return f"{base.rstrip('/')}/{rel_name}"


_CURRENT_JSONAPI_CONTEXT: ContextVar[Optional[JsonApiContext]] = ContextVar("safrs_jsonapi_context", default=None)


def set_jsonapi_context(context: JsonApiContext) -> Token[Optional[JsonApiContext]]:
    return _CURRENT_JSONAPI_CONTEXT.set(context)


def reset_jsonapi_context(token: Token[Optional[JsonApiContext]]) -> None:
    try:
        _CURRENT_JSONAPI_CONTEXT.reset(token)
    except ValueError:
        _CURRENT_JSONAPI_CONTEXT.set(None)


def maybe_jsonapi_context() -> Optional[JsonApiContext]:
    return _CURRENT_JSONAPI_CONTEXT.get()


def get_jsonapi_context() -> JsonApiContext:
    ctx = maybe_jsonapi_context()
    if ctx is None:
        raise RuntimeError("jsonapi context is not set")
    return ctx
