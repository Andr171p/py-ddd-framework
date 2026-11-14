from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from ddf.application.dsl import Condition, Group
from tests.helpers.dsl.expressions import condition, group

SCALAR_OPERATORS = ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte")
LIST_OPERATORS = ("$in", "$nin")
TEXT_OPERATORS = ("$like", "$ilike")
NULL_OPERATORS = ("$isNull", "$isNotNull")
LOGIC_OPERATORS = ("$and", "$or")
BIG_INT = int("9" * 30)
SAMPLE_UUID = UUID("550e8400-e29b-41d4-a716-446655440000")
SAMPLE_MOMENT = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.mark.parametrize("op", SCALAR_OPERATORS)
def test_scalar_operators_accept_a_scalar(parse, op):
    model = parse(condition("priority", op, 0))

    assert isinstance(model, Condition)
    assert model.op == op
    assert model.value == 0


@pytest.mark.parametrize("op", LIST_OPERATORS)
def test_list_operators_accept_a_list(parse, op):
    model = parse(condition("status", op, ["open", "open"]))

    assert model.value == ["open", "open"]


@pytest.mark.parametrize("op", TEXT_OPERATORS)
def test_text_operators_accept_a_string(parse, op):
    model = parse(condition("title", op, "%café%"))

    assert model.value == "%café%"


@pytest.mark.parametrize("op", NULL_OPERATORS)
def test_null_operators_do_not_require_a_value(parse, op):
    model = parse(condition("assigneeName", op, with_value=False))

    assert model.value is None
    assert parse(model.model_dump(mode="json", by_alias=True)) == model


@pytest.mark.parametrize("op", LOGIC_OPERATORS)
def test_groups_accept_logic_operators(parse, op):
    child = condition("status", "$eq", "open")
    model = parse(group(op, child))

    assert isinstance(model, Group)
    assert model.op == op
    assert len(model.filters) == 1


def test_parser_accepts_an_empty_group(parse):
    model = parse(group("$and"))

    assert isinstance(model, Group)
    assert model.filters == ()


@pytest.mark.parametrize("value", [None, 0, False, "", "café принтер", BIG_INT, 1.5])
def test_scalar_boundaries_round_trip(parse, value):
    model = parse(condition("status", "$eq", value))

    assert model.value == value
    assert type(model.value) is type(value)
    assert parse(model.model_dump(mode="json", by_alias=True)) == model


@pytest.mark.parametrize("value", [SAMPLE_UUID, SAMPLE_MOMENT, Decimal("1.50")])
def test_rich_python_values_are_accepted_and_json_emits_strings(parse, value):
    model = parse(condition("id", "$eq", value))
    restored = parse(model.model_dump(mode="json", by_alias=True))

    assert model.value == value
    assert isinstance(restored.value, str)


def test_naive_datetime_is_rejected(parse):
    with pytest.raises(ValidationError):
        parse(condition("dueAt", "$eq", datetime(2026, 3, 1)))


@pytest.mark.parametrize(
    "payload",
    [
        condition("status", "$regex", "open"),
        condition("status", "$and", "open"),
        group("$eq", condition("status", "$eq", "open")),
        {"field": "status", "value": "open"},
        {"op": "$and"},
        {"filter": None},
        {"filters": []},
    ],
    ids=[
        "unknown",
        "logic-in-condition",
        "compare-in-group",
        "missing-op",
        "missing-filters",
        "null-filter",
        "no-op",
    ],
)
def test_unknown_shape_is_rejected(parse, payload):
    with pytest.raises(ValidationError):
        parse(payload)
