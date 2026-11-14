import pytest
from pydantic import ValidationError

from tests.helpers.dsl.expressions import condition, group, search

FIELD_LIMIT = 64
QUERY_LIMIT = 256


@pytest.mark.security
@pytest.mark.parametrize(
    "payload",
    [
        {"field": "status", "filters": [], "op": "$and"},
        {"query": "printer", "field": "status"},
        {"filter": {"query": "printer"}, "op": "$and"},
        {},
        {"extra": 1},
        {**condition("status", "$eq", "open"), "kind": "condition"},
        {**group("$and", condition("status", "$eq", "open")), "note": "x"},
        {"field": "status", "op": "$eq", "value": "open", "filters": []},
    ],
    ids=[
        "field-and-filters",
        "query-and-field",
        "filter-and-op",
        "empty",
        "no-marker",
        "extra-kind",
        "extra-note",
        "condition-and-filters",
    ],
)
def test_ambiguous_payload_is_rejected(parse, payload):
    with pytest.raises(ValidationError) as caught:
        parse(payload)

    assert "Traceback" not in str(caught.value)


@pytest.mark.security
@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (condition("", "$eq", "open"), ValidationError),
        (condition("s" * (FIELD_LIMIT + 1), "$eq", "open"), ValidationError),
        (search(""), ValidationError),
        (search("q" * (QUERY_LIMIT + 1)), ValidationError),
        (condition("status", "$eq", {"$ne": None}), ValidationError),
        (condition("status", "$in", ["open", {"$gt": 1}]), ValidationError),
    ],
    ids=[
        "empty-field",
        "long-field",
        "empty-query",
        "long-query",
        "operator-object",
        "nested-operator-object",
    ],
)
def test_hostile_payload_is_a_validation_error(parse, payload, error):
    with pytest.raises(error) as caught:
        parse(payload)

    text = str(caught.value)
    assert "Traceback" not in text
    assert "postgres" not in text.lower()
    assert "mongodb" not in text.lower()


@pytest.mark.security
def test_limits_still_accept_the_boundary(parse):
    assert parse(condition("s" * FIELD_LIMIT, "$eq", "open")).field == "s" * FIELD_LIMIT
    assert parse(search("q" * QUERY_LIMIT)).query == "q" * QUERY_LIMIT


@pytest.mark.security
@pytest.mark.parametrize("value", ["$ne", "$where", "' OR 1=1 --", '{"$gt": 1}', "100%_"])
def test_dangerous_text_stays_a_value(parse, value):
    model = parse(condition("title", "$eq", value))

    assert model.value == value
    assert parse(model.model_dump(mode="json", by_alias=True)).value == value
