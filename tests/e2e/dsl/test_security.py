import pytest
from fastapi import status
from httpx import Response

from tests.helpers.dsl.cases import require_case
from tests.helpers.dsl.dataset import INTERNAL_NOTE_PREFIX, by_code, load_tickets
from tests.helpers.dsl.expressions import condition, group, negate, search

RECOVERY_ATTEMPTS = 5
OVERSIZED_VALUE = "x" * 100_000
HOSTILE_FIELDS = ("internalNote", "organizationId", "deletedAt", "code", "__dict__", "status.name")


pytestmark = pytest.mark.security


@pytest.mark.parametrize("field", HOSTILE_FIELDS)
async def test_private_fields_are_rejected(client, field):
    response = await client.post("/tickets/search", json=condition(field, "$eq", "x"))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    _assert_safe(response)


@pytest.mark.parametrize(
    "payload",
    [
        {"field": "status", "op": "$nope", "value": "open"},
        {"field": "status", "filters": []},
        {"op": "$and", "filters": []},
        group("$and"),
        condition("title", "$in", "open"),
        condition("title", "$like", 2),
    ],
    ids=["unknown-op", "ambiguous", "empty-group", "empty-group-builder", "scalar-in", "like-number"],
)
async def test_invalid_dsl_is_a_client_error(client, payload):
    response = await client.post("/tickets/search", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    _assert_safe(response)


async def test_quote_payload_does_not_widen_the_result(client):
    title = by_code("quote").title

    exact = await client.post("/tickets/search", json=condition("title", "$eq", title))
    pattern = await client.post("/tickets/search", json=condition("title", "$like", title))
    listed = await client.post("/tickets/search", json=condition("status", "$in", ["open", title]))

    assert exact.status_code == status.HTTP_200_OK
    assert _codes(exact) == {"quote"}
    assert pattern.status_code == status.HTTP_200_OK
    assert _codes(pattern) == {"quote"}
    assert listed.status_code == status.HTTP_200_OK
    assert _codes(listed) == require_case("status-open").codes


async def test_a_broad_query_does_not_leak_private_data(client):
    payload = group("$or", condition("status", "$eq", "open"), negate(condition("status", "$eq", "open")))
    response = await client.post("/tickets/search", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == {ticket.code for ticket in load_tickets()}
    assert INTERNAL_NOTE_PREFIX not in response.text
    for item in response.json()["items"]:
        assert "internalNote" not in item
        assert "organizationId" not in item


async def test_unknown_sort_field_is_rejected(client):
    response = await client.post(
        "/tickets/search",
        params={"field": "internalNote", "direction": "asc"},
        json=condition("status", "$eq", "open"),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    _assert_safe(response)


async def test_service_recovers_after_rejected_requests(client):
    for _ in range(RECOVERY_ATTEMPTS):
        rejected = await client.post("/tickets/search", json={"field": "status"})
        assert rejected.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    opened = require_case("status-open")
    response = await client.post("/tickets/search", json=opened.expression)

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == opened.codes


async def test_search_quote_does_not_match_every_row(client):
    query = "' OR 1=1 --"
    expected = {ticket.code for ticket in load_tickets() if query.casefold() in ticket.title.casefold()}
    response = await client.post("/tickets/search", json=search(query))

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == expected
    assert expected != {ticket.code for ticket in load_tickets()}


@pytest.mark.slow
async def test_large_value_does_not_crash(client):
    response = await client.post("/tickets/search", json=condition("title", "$eq", OVERSIZED_VALUE))

    assert response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
    _assert_safe(response)


def _codes(response: Response) -> set[str]:
    return {item["code"] for item in response.json()["items"]}


def _assert_safe(response: Response) -> None:
    text = response.text
    assert "Traceback" not in text
    assert "postgresql" not in text.lower()
    assert "asyncpg" not in text.lower()
    assert INTERNAL_NOTE_PREFIX not in text
    assert "dsl-e2e-secret" not in text
