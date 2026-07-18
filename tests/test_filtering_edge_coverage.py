import pytest

from safrs.errors import ValidationError
from safrs import filtering


class ComparableAttribute:
    def _result(self, op, value):
        return op, value

    def __eq__(self, value):
        return self._result("eq", value)

    def __ne__(self, value):
        return self._result("ne", value)

    def __lt__(self, value):
        return self._result("lt", value)

    def __le__(self, value):
        return self._result("le", value)

    def __gt__(self, value):
        return self._result("gt", value)

    def __ge__(self, value):
        return self._result("ge", value)

    def like(self, value):
        return self._result("like", value)

    def ilike(self, value):
        return self._result("ilike", value)

    def match(self, value):
        return self._result("match", value)

    def notilike(self, value):
        return self._result("notilike", value)

    def in_(self, value):
        return self._result("in", value)

    def notin_(self, value):
        return self._result("notin", value)

    def is_(self, value):
        return self._result("is", value)

    def is_not(self, value):
        return self._result("is_not", value)


ATTRIBUTE = ComparableAttribute()


class FilterModel:
    id = ATTRIBUTE
    _s_jsonapi_attrs = {"field": ATTRIBUTE}


@pytest.mark.parametrize(
    "node, message",
    [
        ("not an object", "expected object"),
        ({"and": [{}], "or": [{}]}, "expected exactly one"),
        ({"and": [{}], "extra": True}, "unknown keys"),
    ],
)
def test_grouped_filter_rejects_invalid_node_shapes(node, message):
    with pytest.raises(ValidationError) as exc:
        filtering._parse_grouped_node(node)
    assert message in exc.value.message


@pytest.mark.parametrize(
    "node, message",
    [
        ("not an object", "expected clause object"),
        ({"name": "field", "op": "eq", "extra": True}, "unknown keys"),
        ({"name": "", "op": "eq"}, "unknown attribute"),
        ({"name": "field", "op": None}, "unknown operator"),
    ],
)
def test_filter_clause_rejects_invalid_node_shapes(node, message):
    with pytest.raises(ValidationError) as exc:
        filtering._parse_clause_node(node)
    assert message in exc.value.message


def test_filter_compiler_rejects_unknown_node_and_legacy_membership_operator():
    with pytest.raises(ValidationError) as exc:
        filtering._compile_node_to_expression(FilterModel, object())
    assert "Invalid filter node" in exc.value.message

    class MissingMembershipModel:
        _s_jsonapi_attrs = {"field": object()}

    with pytest.raises(ValidationError) as exc:
        filtering._apply_legacy_payload(
            MissingMembershipModel,
            {"name": "field", "op": "in", "val": [1]},
            object(),
        )
    assert "unknown operator" in exc.value.message


@pytest.mark.parametrize("op", ["ne", "lt", "le", "gt", "ge"])
def test_simple_comparison_operators(op):
    expression = filtering._compile_simple_comparison_expression(ATTRIBUTE, op, 3)
    assert expression == (op, 3)


def test_string_and_membership_operators_validate_and_dispatch():
    clause = {"name": "field", "op": "like", "val": "value"}
    assert filtering._compile_string_clause_expression(
        ATTRIBUTE, "like", "value", clause, strict_mode=True
    ) == ("like", "value")

    with pytest.raises(ValidationError) as exc:
        filtering._compile_string_clause_expression(
            object(), "like", "value", clause, strict_mode=True
        )
    assert "unknown operator" in exc.value.message
    with pytest.raises(ValidationError) as exc:
        filtering._compile_string_clause_expression(
            ATTRIBUTE, "like", 42, clause, strict_mode=True
        )
    assert "requires a string" in exc.value.message

    membership_clause = {"name": "field", "op": "in", "val": [1, 2]}
    assert filtering._compile_clause_expression(
        FilterModel, membership_clause, strict_mode=True
    ) == ("in", [1, 2])
    with pytest.raises(ValidationError) as exc:
        filtering._compile_membership_clause_expression(
            ATTRIBUTE, "in", "not-an-array", membership_clause, strict_mode=True
        )
    assert "requires an array" in exc.value.message
    with pytest.raises(ValidationError) as exc:
        filtering._compile_membership_clause_expression(
            object(), "in", [1], membership_clause, strict_mode=True
        )
    assert "unknown operator" in exc.value.message
    assert filtering._compile_membership_clause_expression(
        ATTRIBUTE, "notin", {1, 2}, membership_clause, strict_mode=True
    ) == ("notin", {1, 2})


def test_identity_operators_dispatch_or_fall_through():
    assert filtering._compile_clause_expression(
        FilterModel,
        {"name": "field", "op": "is", "val": None},
        strict_mode=True,
    ) == ("is", None)
    assert filtering._compile_identity_clause_expression(ATTRIBUTE, "is_", None) == (
        "is",
        None,
    )
    assert filtering._compile_identity_clause_expression(ATTRIBUTE, "is_not", None) == (
        "is_not",
        None,
    )
    assert filtering._compile_identity_clause_expression(ATTRIBUTE, "unknown", None) is None
    assert filtering._compile_identity_clause_expression(object(), "is", None) is None


def test_operator_attribute_and_sequence_helpers_cover_edge_values():
    assert filtering._normalized_op_name(None) == ""
    assert filtering._resolve_filter_attr(FilterModel, {"name": "id"}, "id") is ATTRIBUTE

    for invalid_name in (None, ""):
        with pytest.raises(ValidationError) as exc:
            filtering._resolve_filter_attr(FilterModel, {"name": invalid_name}, invalid_name)
        assert "unknown attribute" in exc.value.message

    assert not filtering._is_sequence_like("abc")
    assert filtering._is_sequence_like([1])
    assert filtering._is_sequence_like({1})
    assert not filtering._is_sequence_like(1)
