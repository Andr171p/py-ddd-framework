import copy

from ddf.application.dsl import Condition, Group, Negation, Search
from tests.helpers.dsl.expressions import condition, group, negate, search


def test_markers_select_the_node(parse):
    assert isinstance(parse(condition("status", "$eq", "open")), Condition)
    assert isinstance(parse(group("$and", condition("status", "$eq", "open"))), Group)
    assert isinstance(parse(negate(condition("status", "$eq", "closed"))), Negation)
    assert isinstance(parse(search("принтер")), Search)


def test_nested_tree_keeps_order(parse):
    left = condition("status", "$eq", "open")
    right = condition("priority", "$gt", 2)
    payload = group("$and", group("$or", left, right), search("принтер"))

    model = parse(payload)

    assert isinstance(model, Group)
    assert model.op == "$and"
    nested = model.filters[0]
    assert isinstance(nested, Group)
    assert [item.model_dump(mode="json", by_alias=True) for item in nested.filters] == [left, right]
    assert isinstance(model.filters[1], Search)


def test_public_json_uses_the_filter_alias(parse):
    model = parse(negate(condition("status", "$eq", "closed")))
    dumped = model.model_dump(mode="json", by_alias=True)

    assert set(dumped) == {"filter"}
    assert parse(dumped) == model


def test_round_trip_keeps_the_tree(parse):
    payload = group(
        "$or",
        condition("status", "$in", ["open", "pending"]),
        negate(condition("urgent", "$eq", False)),
        search("café"),
    )
    model = parse(payload)

    assert parse(model.model_dump(mode="json", by_alias=True)) == model
    assert parse(payload) == model


def test_parsing_does_not_mutate_the_input(parse):
    payload = group("$and", condition("status", "$eq", "open"), search("принтер"))
    snapshot = copy.deepcopy(payload)

    parse(payload)

    assert payload == snapshot
