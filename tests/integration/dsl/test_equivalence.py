from datetime import UTC, datetime

import pytest

from tests.helpers.dsl.cases import load_null_cases, load_shared_cases
from tests.helpers.dsl.dataset import by_code, load_tickets
from tests.helpers.dsl.expressions import condition

DUE_CUTOFF = datetime(2026, 3, 1, tzinfo=UTC)
SHARED = load_shared_cases()
NULLS = load_null_cases()


@pytest.mark.parametrize("case", SHARED, ids=[case.name for case in SHARED])
async def test_shared_contract(postgres, mongo, case):
    assert await postgres.codes(case.expression) == case.codes
    assert await mongo.codes(case.expression) == case.codes


@pytest.mark.parametrize("case", NULLS, ids=[case.name for case in NULLS])
async def test_null_and_missing_contract(postgres, mongo, case):
    assert await postgres.codes(case.expression) == case.postgres
    assert await mongo.codes(case.expression) == case.mongo


async def test_due_dates_use_the_same_cutoff(postgres, mongo):
    expected = {
        ticket.code for ticket in load_tickets() if ticket.due_at is not None and ticket.due_at >= DUE_CUTOFF
    }
    payload = condition("dueAt", "$gte", DUE_CUTOFF)

    assert await postgres.codes(payload) == expected
    assert await mongo.codes(payload) == expected


async def test_uuid_identity_matches(postgres, mongo):
    ticket = by_code("ada")
    others = {item.code for item in load_tickets()} - {ticket.code}

    assert await postgres.codes(condition("id", "$eq", ticket.id)) == {ticket.code}
    assert await mongo.codes(condition("id", "$eq", ticket.id)) == {ticket.code}
    assert await postgres.codes(condition("id", "$ne", ticket.id)) == others
    assert await mongo.codes(condition("id", "$ne", ticket.id)) == others
