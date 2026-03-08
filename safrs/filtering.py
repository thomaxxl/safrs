from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

import safrs
from sqlalchemy import and_, not_, or_

from .errors import ValidationError

_FILTER_FORMAT_ERROR = "Invalid filter format (see https://github.com/thomaxxl/safrs/wiki)"
_GROUP_KEYS = ("and", "or", "not")
_LEAF_KEYS = {"name", "op", "val"}


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


def apply_filter_json(cls: Any, raw_filter: str, query: Any) -> Any:
    parsed = parse_filter_json(raw_filter)
    if isinstance(parsed, LegacyPayload):
        return _apply_legacy_payload(cls, parsed.raw, query)
    expression = _compile_node_to_expression(cls, parsed)
    return query.filter(expression)


def parse_filter_json(raw_filter: str) -> ParsedFilter:
    try:
        decoded = json.loads(raw_filter)
    except json.decoder.JSONDecodeError:
        raise ValidationError(_FILTER_FORMAT_ERROR)

    if isinstance(decoded, dict) and _contains_group_key(decoded):
        return _parse_grouped_node(decoded)
    return LegacyPayload(decoded)


def _contains_group_key(node: dict[str, Any]) -> bool:
    return any(key in node for key in _GROUP_KEYS)


def _parse_grouped_node(node: Any) -> FilterNode:
    if not isinstance(node, dict):
        raise ValidationError(f'Invalid filter "{node}", expected object')

    group_keys = [key for key in _GROUP_KEYS if key in node]
    if not group_keys:
        return _parse_clause_node(node)
    if len(group_keys) != 1:
        raise ValidationError(f'Invalid filter "{node}", expected exactly one of and/or/not')

    group_key = group_keys[0]
    unknown_keys = [key for key in node if key != group_key]
    if unknown_keys:
        raise ValidationError(f'Invalid filter "{node}", unknown keys {unknown_keys}')

    payload = node[group_key]
    if group_key in {"and", "or"}:
        if not isinstance(payload, list) or not payload:
            raise ValidationError(f'Invalid filter "{node}", "{group_key}" requires a non-empty array')
        children = [_parse_grouped_node(child) for child in payload]
        if group_key == "and":
            return AndNode(children)
        return OrNode(children)

    if isinstance(payload, list):
        raise ValidationError(f'Invalid filter "{node}", "not" requires a single object')
    return NotNode(_parse_grouped_node(payload))


def _parse_clause_node(node: Any) -> ClauseNode:
    if not isinstance(node, dict):
        raise ValidationError(f'Invalid filter "{node}", expected clause object')
    unknown = [key for key in node if key not in _LEAF_KEYS]
    if unknown:
        raise ValidationError(f'Invalid filter "{node}", unknown keys {unknown}')

    name = node.get("name")
    op = node.get("op")
    if not isinstance(name, str) or not name:
        raise ValidationError(f'Invalid filter "{node}", unknown attribute "{name}"')
    if not isinstance(op, str) or not op:
        raise ValidationError(f'Invalid filter "{node}", unknown operator "{op}"')
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
    raise ValidationError(f'Invalid filter node "{node}"')


def _apply_legacy_payload(cls: Any, payload: Any, query: Any) -> Any:
    filters = payload if isinstance(payload, list) else [payload]
    expressions: list[Any] = []

    for filt in filters:
        if not isinstance(filt, dict):
            safrs.log.warning(f"Invalid filter '{filt}'")
            continue

        op_name = _normalized_op_name(filt.get("op"))
        attr = _resolve_filter_attr(cls, filt, filt.get("name"))
        value = filt.get("val")

        if op_name in {"in", "notin"}:
            op = getattr(attr, op_name + "_", None)
            if not callable(op):
                raise ValidationError(f'Invalid filter "{filt}", unknown operator "{op_name}"')
            query = query.filter(op(value))
            continue

        expressions.append(_compile_clause_expression(cls, filt, strict_mode=False))

    return query.filter(or_(*expressions))


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

    raise ValidationError(f'Invalid filter "{clause}", unknown operator "{op_name}"')


def _compile_string_clause_expression(
    attr: Any, op_name: str, value: Any, clause: dict[str, Any], *, strict_mode: bool
) -> Any:
    op = getattr(attr, op_name, None)
    if not callable(op):
        raise ValidationError(f'Invalid filter "{clause}", unknown operator "{op_name}"')
    if strict_mode and not isinstance(value, str):
        raise ValidationError(f'Invalid filter "{clause}", "{op_name}" requires a string value')
    return op(value)


def _compile_membership_clause_expression(
    attr: Any, op_name: str, value: Any, clause: dict[str, Any], *, strict_mode: bool
) -> Any:
    if strict_mode and not _is_sequence_like(value):
        raise ValidationError(f'Invalid filter "{clause}", "{op_name}" requires an array value')
    op = getattr(attr, op_name + "_", None)
    if not callable(op):
        raise ValidationError(f'Invalid filter "{clause}", unknown operator "{op_name}"')
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
        raise ValidationError(f'Invalid filter "{clause}", unknown attribute "{attr_name}"')
    if "." in attr_name:
        raise ValidationError(
            f'Invalid filter "{clause}", relationship-path filtering is not supported for "{attr_name}"'
        )
    if attr_name == "id":
        return cls.id
    if attr_name not in cls._s_jsonapi_attrs:
        raise ValidationError(f'Invalid filter "{clause}", unknown attribute "{attr_name}"')
    return cls._s_jsonapi_attrs[attr_name]


def _is_sequence_like(value: Any) -> bool:
    if isinstance(value, (str, bytes)):
        return False
    if isinstance(value, Sequence):
        return True
    return isinstance(value, set)
