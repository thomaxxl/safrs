from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence, TypeVar

import safrs
from sqlalchemy import and_, not_, or_
from sqlalchemy.exc import ArgumentError

from .jsonapi_attr import is_jsonapi_attr

from .errors import ValidationError
from .config import get_config

_FILTER_FORMAT_ERROR = "Invalid filter format (see https://github.com/thomaxxl/safrs/wiki)"
_GROUP_KEYS = ("and", "or", "not")
_LEAF_KEYS = {"name", "op", "val"}
_BRACKET_FILTER_RE = re.compile(r"filter\[([^\[\]]+)\]")


@dataclass(frozen=True)
class ClauseNode:
    name: str
    op: str
    val: Any
    raw: dict[str, Any]


@dataclass(frozen=True)
class AndNode:
    items: list["FilterNode"]


@dataclass(frozen=True)
class OrNode:
    items: list["FilterNode"]


@dataclass(frozen=True)
class NotNode:
    item: "FilterNode"


@dataclass(frozen=True)
class LegacyPayload:
    raw: Any


FilterNode = ClauseNode | AndNode | OrNode | NotNode
ParsedFilter = FilterNode | LegacyPayload
FilterCallable = TypeVar("FilterCallable", bound=Callable[..., Any])


def jsonapi_filter_fields(*field_names: str) -> Callable[[FilterCallable], FilterCallable]:
    """Declare every model field a custom ``filter`` callable may inspect."""
    def decorate(function: FilterCallable) -> FilterCallable:
        setattr(function, "safrs_filter_fields", tuple(field_names))
        return function

    return decorate


def custom_filter_read_fields(cls: Any, custom_filter: Any) -> tuple[str, ...]:
    """Validate and return the declared read set for a custom filter."""
    function = getattr(custom_filter, "__func__", custom_filter)
    fields = getattr(custom_filter, "safrs_filter_fields", None)
    if fields is None:
        fields = getattr(function, "safrs_filter_fields", None)
    if fields is None:
        raise ValidationError(
            "Custom filters must declare readable fields with @jsonapi_filter_fields(...)"
        )
    names = tuple(str(name) for name in fields)
    denied = [name for name in names if get_filterable_attribute(cls, name) is None]
    if denied:
        raise ValidationError(f"Custom filter uses protected fields: {', '.join(denied)}")
    return names


def get_filterable_attribute(cls: Any, attr_name: str) -> Any:
    """Return a readable/filterable model attribute, or ``None`` when denied.

    Filtering is an observable read operation: matching rows and collection
    counts reveal information even when an attribute is omitted from the
    serialized response.  Every built-in filter entry point uses this helper
    so ``_s_check_perm``/``_s_jsonapi_attrs`` and the column ``filterable``
    flag are authorization boundaries, not documentation-only hints.
    """

    if not isinstance(attr_name, str) or not attr_name or "." in attr_name:
        return None

    exposed_attr: Any = None
    if attr_name == "id":
        exposed_attr = getattr(cls, "id", None)
        if exposed_attr is None:
            id_type = getattr(cls, "id_type", None)
            primary_keys: Sequence[Any] = getattr(id_type, "primary_keys", []) if id_type is not None else []
            if len(primary_keys) == 1:
                exposed_attr = getattr(cls, primary_keys[0], None)
    else:
        jsonapi_attrs = getattr(cls, "_s_jsonapi_attrs", {})
        if attr_name not in jsonapi_attrs:
            return None
        exposed_attr = jsonapi_attrs[attr_name]

    column_dict = getattr(cls, "_s_column_dict", {}) or {}
    column = column_dict.get(attr_name, exposed_attr)
    if getattr(exposed_attr, "filterable", True) is False or getattr(column, "filterable", True) is False:
        return None
    return getattr(cls, attr_name, exposed_attr)


def parse_bracket_filter_name(raw_key: Any) -> str | None:
    """Return a bracket-filter attribute name and reject malformed filter keys."""
    key = str(raw_key)
    if not key.startswith("filter["):
        return None
    match = _BRACKET_FILTER_RE.fullmatch(key)
    if match is None:
        raise ValidationError("Invalid bracket filter parameter")
    return match.group(1)


def require_filterable_attribute(cls: Any, attr_name: str) -> Any:
    """Resolve an attribute supported by exact-value bracket filtering.

    Unknown, unreadable, non-filterable, and computed attributes deliberately
    share one error.  This prevents protected model metadata from becoming an
    attribute-discovery oracle.  Computed ``jsonapi_attr`` values need an
    explicit custom filter because they do not necessarily have a SQL form.
    """
    attr = get_filterable_attribute(cls, attr_name)
    if attr is None or is_jsonapi_attr(attr):
        raise ValidationError(f'Invalid filter, unknown attribute "{attr_name}"')
    return attr


def filter_attribute_names(raw_filter: str) -> set[str]:
    """Return every attribute referenced by a built-in JSON filter."""

    parsed = parse_filter_json(raw_filter)
    if isinstance(parsed, LegacyPayload):
        filters = parsed.raw if isinstance(parsed.raw, list) else [parsed.raw]
        return {
            name
            for item in filters
            if isinstance(item, dict) and isinstance((name := item.get("name")), str) and name
        }
    return _node_attribute_names(parsed)


def uses_builtin_json_filter(cls: Any) -> bool:
    """Whether ``cls._s_filter`` is SAFRS' structured JSON implementation."""

    current = getattr(cls, "_s_filter", None)
    builtin = getattr(getattr(safrs, "SAFRSBase", None), "_s_filter", None)
    return getattr(current, "__func__", current) is getattr(builtin, "__func__", builtin)


def apply_filter_read_permissions(cls: Any, result: Any, attr_names: Iterable[str]) -> Any:
    """Remove matches that cannot read every field used by the filter.

    A class-level permission check controls whether a field may be queried at
    all.  Models may additionally implement row-dependent permissions in the
    instance side of the ``_s_check_perm`` hybrid.  SQL cannot express that
    arbitrary Python policy, so only those models are materialized and checked
    before counts and pagination are calculated.  Other models keep their
    database query unchanged.
    """

    names = tuple(dict.fromkeys(name for name in attr_names if name != "id"))
    if not names or not _has_custom_instance_permission_check(cls):
        return result

    items = materialize_for_authorization(result)

    authorized: list[Any] = []
    for item in items:
        check_perm = getattr(item, "_s_check_perm", None)
        if not callable(check_perm):
            continue
        try:
            if all(bool(check_perm(name, "r")) for name in names):
                authorized.append(item)
        except Exception as exc:  # A failing authorization hook must fail closed.
            safrs.log.warning(
                "Filter permission check failed for %s (%s)",
                type(item).__name__,
                type(exc).__name__,
            )
    return authorized


def materialize_for_authorization(result: Any) -> list[Any]:
    """Materialize a policy scan with a configurable fail-closed bound."""
    max_items = int(get_config("MAX_AUTHORIZATION_SCAN") or 0)
    if hasattr(result, "all") and callable(result.all):
        bounded = result.limit(max_items + 1) if max_items > 0 and hasattr(result, "limit") else result
        items = list(bounded.all())
    elif isinstance(result, (list, tuple, set)):
        items = list(result)
    else:
        items = [result] if result is not None else []
    if max_items > 0 and len(items) > max_items:
        raise ValidationError(
            f"Authorization scan exceeds maximum resource count {max_items}; implement _s_query_scope"
        )
    return items


def validate_filter_value_count(raw_value: Any) -> None:
    """Bound comma-separated bracket filter membership values."""
    max_values = int(get_config("MAX_FILTER_VALUES") or 0)
    if max_values > 0 and len(str(raw_value).split(",")) > max_values:
        raise ValidationError(f"Filter value list exceeds maximum size {max_values}")


def validate_bracket_filter_count(filters: Any) -> None:
    """Bound the number of exact-value filters in the active app context."""
    max_filters = int(get_config("MAX_BRACKET_FILTERS") or 0)
    if max_filters > 0 and len(filters) > max_filters:
        raise ValidationError(
            f"Too many bracket filters (maximum {max_filters})"
        )


def coerce_filter_values(model_attr: Any, raw_value: Any, attr_name: str) -> list[Any]:
    """Parse a non-empty CSV filter value list using the model column type."""
    validate_filter_value_count(raw_value)
    values = [part.strip() for part in str(raw_value).split(",")]
    if not values or any(not value for value in values):
        raise ValidationError(f'Filter for attribute "{attr_name}" requires a value')

    try:
        model_type = model_attr.type.python_type
    except (AttributeError, NotImplementedError):
        return values
    if model_type in {dict, list}:
        return values

    coerced: list[Any] = []
    for value in values:
        try:
            if model_type is bool:
                lowered = value.lower()
                if lowered in {"1", "true", "yes", "on"}:
                    coerced.append(True)
                    continue
                if lowered in {"0", "false", "no", "off"}:
                    coerced.append(False)
                    continue
                raise ValueError("invalid boolean")
            if model_type is dt.datetime:
                coerced.append(dt.datetime.fromisoformat(value))
            elif model_type is dt.date:
                coerced.append(dt.date.fromisoformat(value))
            elif model_type is dt.time:
                coerced.append(dt.time.fromisoformat(value))
            else:
                coerced.append(model_type(value))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError(
                f'Invalid filter value for attribute "{attr_name}"'
            ) from exc
    return coerced


def bracket_filter_expression(model_attr: Any, values: list[Any], attr_name: str) -> Any:
    """Build an exact-value expression while normalizing client value errors."""
    try:
        if hasattr(model_attr, "in_"):
            return model_attr.in_(values)
        return model_attr == values[0]
    except (ArgumentError, TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(
            f'Invalid filter value for attribute "{attr_name}"'
        ) from exc


def validate_filter_result(result: Any) -> Any:
    """Reject custom filters that return neither a query nor a collection."""
    if (hasattr(result, "all") and callable(result.all)) or isinstance(
        result, (list, tuple, set)
    ):
        return result
    raise ValidationError("Invalid filter result")


def _has_custom_instance_permission_check(cls: Any) -> bool:
    owner = next((base for base in getattr(cls, "__mro__", ()) if "_s_check_perm" in base.__dict__), None)
    if owner is None:
        return False
    return owner is not getattr(safrs, "SAFRSBase", None)


def has_custom_instance_permission_check(cls: Any) -> bool:
    """Whether field visibility can vary between rows of ``cls``."""
    return _has_custom_instance_permission_check(cls)


def _node_attribute_names(node: FilterNode) -> set[str]:
    if isinstance(node, ClauseNode):
        return {node.name}
    if isinstance(node, NotNode):
        return _node_attribute_names(node.item)
    names: set[str] = set()
    for item in node.items:
        names.update(_node_attribute_names(item))
    return names


def apply_filter_json(cls: Any, raw_filter: str, query: Any) -> Any:
    parsed = parse_filter_json(raw_filter)
    try:
        if isinstance(parsed, LegacyPayload):
            return _apply_legacy_payload(cls, parsed.raw, query)
        expression = _compile_node_to_expression(cls, parsed)
        return query.filter(expression)
    except ValidationError:
        raise
    except (ArgumentError, TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("Invalid filter value") from exc


def parse_filter_json(raw_filter: str) -> ParsedFilter:
    max_length = int(get_config("MAX_FILTER_LENGTH") or 0)
    if max_length > 0 and len(raw_filter) > max_length:
        raise ValidationError(f"Filter exceeds maximum length {max_length}")
    try:
        decoded = json.loads(raw_filter)
    except json.decoder.JSONDecodeError:
        raise ValidationError(_FILTER_FORMAT_ERROR)
    _validate_filter_complexity(decoded)

    if isinstance(decoded, dict) and _contains_group_key(decoded):
        return _parse_grouped_node(decoded)
    _validate_legacy_payload(decoded)
    return LegacyPayload(decoded)


def _validate_legacy_payload(payload: Any) -> None:
    filters = payload if isinstance(payload, list) else [payload]
    if not filters or any(not isinstance(item, dict) for item in filters):
        raise ValidationError("Invalid filter, expected a clause object or non-empty array")


def _validate_filter_complexity(payload: Any) -> None:
    """Bound parser/SQL complexity before recursively compiling a filter."""
    max_depth = int(get_config("MAX_FILTER_DEPTH") or 0)
    max_clauses = int(get_config("MAX_FILTER_CLAUSES") or 0)
    max_values = int(get_config("MAX_FILTER_VALUES") or 0)
    clauses = 0
    stack: list[tuple[Any, int]] = [(payload, 1)]
    while stack:
        node, depth = stack.pop()
        if max_depth > 0 and depth > max_depth:
            raise ValidationError(f"Filter exceeds maximum depth {max_depth}")
        if isinstance(node, dict):
            if "name" in node or "op" in node:
                clauses += 1
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
        elif isinstance(node, list):
            if max_values > 0 and len(node) > max_values:
                raise ValidationError(f"Filter array exceeds maximum size {max_values}")
            stack.extend((value, depth + 1) for value in node if isinstance(value, (dict, list)))
        if max_clauses > 0 and clauses > max_clauses:
            raise ValidationError(f"Filter exceeds maximum clause count {max_clauses}")


def _contains_group_key(node: dict[str, Any]) -> bool:
    return any(key in node for key in _GROUP_KEYS)


def _parse_grouped_node(node: Any) -> FilterNode:
    if not isinstance(node, dict):
        raise ValidationError("Invalid filter, expected object")

    group_keys = [key for key in _GROUP_KEYS if key in node]
    if not group_keys:
        return _parse_clause_node(node)
    if len(group_keys) != 1:
        raise ValidationError("Invalid filter, expected exactly one of and/or/not")

    group_key = group_keys[0]
    unknown_keys = [key for key in node if key != group_key]
    if unknown_keys:
        raise ValidationError(f"Invalid filter, unknown keys {unknown_keys}")

    payload = node[group_key]
    if group_key in {"and", "or"}:
        if not isinstance(payload, list) or not payload:
            raise ValidationError(f'Invalid filter, "{group_key}" requires a non-empty array')
        children = [_parse_grouped_node(child) for child in payload]
        if group_key == "and":
            return AndNode(children)
        return OrNode(children)

    if isinstance(payload, list):
        raise ValidationError('Invalid filter, "not" requires a single object')
    return NotNode(_parse_grouped_node(payload))


def _parse_clause_node(node: Any) -> ClauseNode:
    if not isinstance(node, dict):
        raise ValidationError("Invalid filter, expected clause object")
    unknown = [key for key in node if key not in _LEAF_KEYS]
    if unknown:
        raise ValidationError(f"Invalid filter, unknown keys {unknown}")

    name = node.get("name")
    op = node.get("op")
    if not isinstance(name, str) or not name:
        raise ValidationError(f'Invalid filter, unknown attribute "{name}"')
    if not isinstance(op, str) or not op:
        raise ValidationError(f'Invalid filter, unknown operator "{op}"')
    return ClauseNode(name=name, op=op, val=node.get("val"), raw=dict(node))


def _compile_node_to_expression(cls: Any, node: FilterNode) -> Any:
    if isinstance(node, ClauseNode):
        return _compile_clause_expression(cls, node.raw, strict_mode=True)
    if isinstance(node, AndNode):
        return and_(*[_compile_node_to_expression(cls, child) for child in node.items])
    if isinstance(node, OrNode):
        return or_(*[_compile_node_to_expression(cls, child) for child in node.items])
    if isinstance(node, NotNode):
        return not_(_compile_node_to_expression(cls, node.item))
    raise ValidationError("Invalid filter node")


def _apply_legacy_payload(cls: Any, payload: Any, query: Any) -> Any:
    filters = payload if isinstance(payload, list) else [payload]
    expressions: list[Any] = []

    for filt in filters:
        op_name = _normalized_op_name(filt.get("op"))
        attr = _resolve_filter_attr(cls, filt, filt.get("name"))
        value = filt.get("val")

        if op_name in {"in", "notin"}:
            expression = _compile_membership_clause_expression(
                attr, op_name, value, filt, strict_mode=False
            )
            query = query.filter(expression)
            continue

        expressions.append(_compile_clause_expression(cls, filt, strict_mode=False))

    return query.filter(or_(*expressions)) if expressions else query


def _compile_clause_expression(cls: Any, clause: dict[str, Any], *, strict_mode: bool) -> Any:
    attr_name = clause.get("name")
    value = clause.get("val")
    op_name = _normalized_op_name(clause.get("op"))
    attr = _resolve_filter_attr(cls, clause, attr_name)

    if op_name in {"like", "ilike", "match", "notilike"}:
        return _compile_string_clause_expression(attr, op_name, value, clause, strict_mode=strict_mode)

    if op_name in {"in", "notin"}:
        return _compile_membership_clause_expression(attr, op_name, value, clause, strict_mode=strict_mode)

    comparison_expression = _compile_simple_comparison_expression(attr, op_name, value)
    if comparison_expression is not None:
        return comparison_expression

    identity_expression = _compile_identity_clause_expression(attr, op_name, value)
    if identity_expression is not None:
        return identity_expression

    raise ValidationError(f'Invalid filter, unknown operator "{op_name}"')


def _compile_string_clause_expression(
    attr: Any, op_name: str, value: Any, clause: dict[str, Any], *, strict_mode: bool
) -> Any:
    op = getattr(attr, op_name, None)
    if not callable(op):
        raise ValidationError(f'Invalid filter, unknown operator "{op_name}"')
    if not isinstance(value, str):
        raise ValidationError(f'Invalid filter, "{op_name}" requires a string value')
    return op(value)


def _compile_membership_clause_expression(
    attr: Any, op_name: str, value: Any, clause: dict[str, Any], *, strict_mode: bool
) -> Any:
    if not _is_sequence_like(value):
        raise ValidationError(f'Invalid filter, "{op_name}" requires an array value')
    op = getattr(attr, op_name + "_", None)
    if not callable(op):
        raise ValidationError(f'Invalid filter, unknown operator "{op_name}"')
    return op(value)


def _compile_simple_comparison_expression(attr: Any, op_name: str, value: Any) -> Any:
    if op_name == "eq":
        return attr == value
    if op_name == "ne":
        return attr != value
    if op_name == "lt":
        return attr < value
    if op_name == "le":
        return attr <= value
    if op_name == "gt":
        return attr > value
    if op_name == "ge":
        return attr >= value
    return None


def _compile_identity_clause_expression(attr: Any, op_name: str, value: Any) -> Any:
    method_name = ""
    if op_name in {"is", "is_"}:
        method_name = "is_"
    elif op_name == "is_not":
        method_name = "is_not"
    if not method_name:
        return None
    op = getattr(attr, method_name, None)
    if not callable(op):
        return None
    return op(value)


def _normalized_op_name(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip("_")


def _resolve_filter_attr(cls: Any, clause: dict[str, Any], attr_name: Any) -> Any:
    if not isinstance(attr_name, str) or not attr_name:
        raise ValidationError(f'Invalid filter, unknown attribute "{attr_name}"')
    if "." in attr_name:
        raise ValidationError(
            f'Relationship-path filtering is not supported for "{attr_name}"'
        )
    attr = get_filterable_attribute(cls, attr_name)
    if attr is None:
        raise ValidationError(f'Invalid filter, unknown attribute "{attr_name}"')
    return attr


def _is_sequence_like(value: Any) -> bool:
    if isinstance(value, (str, bytes)):
        return False
    if isinstance(value, Sequence):
        return True
    return isinstance(value, set)
