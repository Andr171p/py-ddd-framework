import pytest

from tests.helpers.dsl.cases import require_case
from tests.helpers.dsl.dataset import load_tickets
from tests.helpers.dsl.expressions import condition, group, search


async def test_search_is_rejected(mongo):
    with pytest.raises((TypeError, ValueError)):
        await mongo.codes(search("printer"))


async def test_empty_group_matches_every_document(mongo):
    assert await mongo.codes(group("$or")) == {ticket.code for ticket in load_tickets()}


@pytest.mark.security
async def test_scalar_in_does_not_match_the_whole_token(mongo):
    opened = require_case("status-open").codes

    try:
        found = await mongo.codes(condition("status", "$in", "open"))
    except (TypeError, ValueError):
        return

    assert found.isdisjoint(opened)
