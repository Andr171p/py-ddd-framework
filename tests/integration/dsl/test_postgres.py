import pytest

from tests.helpers.dsl.dataset import load_tickets
from tests.helpers.dsl.expressions import condition, group, search


async def test_search_matches_a_case_insensitive_substring(postgres):
    expected = {ticket.code for ticket in load_tickets() if "printer" in ticket.title.casefold()}

    assert await postgres.codes(search("printer")) == expected


async def test_search_quote_does_not_match_every_row(postgres):
    query = "' OR 1=1 --"
    expected = {ticket.code for ticket in load_tickets() if query.casefold() in ticket.title.casefold()}

    assert expected
    assert await postgres.codes(search(query)) == expected


async def test_search_percent_is_a_like_wildcard(postgres):
    assert await postgres.codes(search("%")) == {ticket.code for ticket in load_tickets()}


async def test_empty_group_is_rejected(postgres):
    with pytest.raises(ValueError):
        await postgres.codes(group("$and"))


async def test_scalar_in_is_rejected(postgres):
    with pytest.raises(ValueError):
        await postgres.codes(condition("status", "$in", "open"))


async def test_non_string_like_is_rejected(postgres):
    with pytest.raises(ValueError):
        await postgres.codes(condition("title", "$like", 2))


async def test_null_check_ignores_a_stray_value(postgres):
    plain = {"field": "assigneeName", "op": "$isNull"}
    stray = {"field": "assigneeName", "op": "$isNull", "value": "' OR 1=1 --"}

    assert await postgres.codes(stray) == await postgres.codes(plain)
