import copy
import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from ddf.application.dsl import Condition, Group, Negation, Search
from tests.helpers.dsl.expressions import condition, group, negate
from tests.helpers.dsl.parsing import parse_expression

TREE_WIDTH = 200
TREE_DEPTH = 32
VALIDATION_BUDGET_SECONDS = 2.0

_TEXT = st.text(alphabet=st.characters(codec="utf-8"), max_size=12)
_VALUES = st.one_of(st.none(), st.booleans(), st.integers(min_value=-20, max_value=20), _TEXT)
_FIELDS = st.sampled_from(("status", "priority", "title", "assigneeName"))

_CONDITIONS = st.fixed_dictionaries(
    {
        "field": _FIELDS,
        "op": st.sampled_from(("$eq", "$ne", "$gt")),
        "value": _VALUES,
    }
)
_LISTS = st.fixed_dictionaries(
    {
        "field": _FIELDS,
        "op": st.sampled_from(("$in", "$nin")),
        "value": st.lists(_VALUES, max_size=3),
    }
)
_NULLS = st.fixed_dictionaries({"field": _FIELDS, "op": st.sampled_from(("$isNull", "$isNotNull"))})
_SEARCHES = st.fixed_dictionaries({"query": _TEXT.filter(bool)})
_LEAVES = st.one_of(_CONDITIONS, _LISTS, _NULLS, _SEARCHES)


def _branches(children: st.SearchStrategy[object]) -> st.SearchStrategy[object]:
    return st.one_of(
        st.fixed_dictionaries(
            {
                "op": st.sampled_from(("$and", "$or")),
                "filters": st.lists(children, max_size=3),
            }
        ),
        st.fixed_dictionaries({"filter": children}),
    )


_EXPRESSIONS = st.recursive(_LEAVES, _branches, max_leaves=8)
_JSON = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(min_value=-20, max_value=20), _TEXT),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(_TEXT, children, max_size=3),
    ),
    max_leaves=8,
)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_EXPRESSIONS)
def test_generated_trees_round_trip(payload: object):
    model = parse_expression(payload)
    assert parse_expression(model.model_dump(mode="json", by_alias=True)) == model


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_EXPRESSIONS)
def test_generated_trees_do_not_mutate_input(payload: dict[str, object]):
    snapshot = _copy(payload)
    model = parse_expression(payload)

    assert payload == snapshot
    with pytest.raises(ValidationError):
        setattr(model, next(iter(type(model).model_fields)), None)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_JSON)
@pytest.mark.security
def test_fuzz_either_parses_or_rejects(payload: object):
    try:
        model = parse_expression(payload)
    except ValidationError as exc:
        assert "Traceback" not in str(exc)
        return

    assert isinstance(model, Condition | Group | Negation | Search)


def test_wide_and_deep_trees_stay_within_budget():
    wide = group("$or", *(condition("status", "$eq", "open") for _ in range(TREE_WIDTH)))
    deep = condition("status", "$eq", "open")
    for _ in range(TREE_DEPTH):
        deep = negate(deep)

    started = time.perf_counter()
    wide_model = parse_expression(wide)
    deep_model = parse_expression(deep)
    elapsed = time.perf_counter() - started

    assert isinstance(wide_model, Group)
    assert len(wide_model.filters) == TREE_WIDTH
    assert isinstance(deep_model, Negation)
    assert parse_expression(wide) == wide_model
    assert parse_expression(deep) == deep_model
    assert elapsed < VALIDATION_BUDGET_SECONDS


def _copy(payload: dict[str, object]) -> dict[str, object]:
    return copy.deepcopy(payload)
