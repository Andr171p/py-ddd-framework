import pytest
from fastapi import status
from httpx import Response

from tests.helpers.dsl.cases import load_null_cases, load_shared_cases
from tests.helpers.dsl.dataset import TicketSeed, by_code, load_tickets
from tests.helpers.dsl.expressions import condition, group, search
from tests.helpers.dsl.paging import SAMPLE_PAGE_SIZE, code_pages, ordered, page_count

SHARED = load_shared_cases()
NULLS = load_null_cases()
PUBLIC_FIELDS = {"code", "title", "status", "priority", "assigneeName", "urgent"}


@pytest.mark.parametrize("case", SHARED, ids=[case.name for case in SHARED])
async def test_shared_cases(client, case):
    response = await client.post("/tickets/search", json=case.expression)

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == case.codes


@pytest.mark.parametrize("case", NULLS, ids=[case.name for case in NULLS])
async def test_postgres_null_contract(client, case):
    response = await client.post("/tickets/search", json=case.expression)

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == case.postgres


def _open(ticket: TicketSeed) -> bool:
    return ticket.status == "open"


async def test_search_can_be_combined_with_a_filter(client):
    payload = group("$and", condition("status", "$eq", "open"), search("printer"))
    expected = {
        ticket.code
        for ticket in load_tickets()
        if ticket.status == "open" and "printer" in ticket.title.casefold()
    }

    response = await client.post("/tickets/search", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert _codes(response) == expected


async def test_response_exposes_only_public_fields(client):
    response = await client.post("/tickets/search", json=condition("title", "$eq", by_code("jam").title))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [item["code"] for item in body["items"]] == ["jam"]
    assert set(body["items"][0]) == PUBLIC_FIELDS
    assert body["items"][0]["assigneeName"] is None


async def test_offset_pages_cover_the_filter_without_gaps(client):
    rows = ordered(_open)
    pages = code_pages(rows, SAMPLE_PAGE_SIZE)
    seen: list[str] = []

    for number, expected in enumerate(pages, start=1):
        response = await client.post(
            "/tickets/search",
            params={
                "pagination": "offset",
                "page": number,
                "size": SAMPLE_PAGE_SIZE,
                "field": "priority",
                "direction": "asc",
            },
            json=condition("status", "$eq", "open"),
        )
        body = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert [item["code"] for item in body["items"]] == list(expected)
        assert body["meta"]["total"] == len(rows)
        assert body["meta"]["page"] == number
        assert body["meta"]["size"] == SAMPLE_PAGE_SIZE
        assert body["meta"]["pages"] == page_count(len(rows), SAMPLE_PAGE_SIZE)
        assert body["meta"]["has_next"] is (number < len(pages))
        assert body["meta"]["has_prev"] is (number > 1)
        seen.extend(item["code"] for item in body["items"])

    assert seen == [ticket.code for ticket in rows]


async def test_empty_filter_returns_an_empty_page(client):
    response = await client.post("/tickets/search", json=condition("status", "$eq", "absent"))
    body = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert body["items"] == []
    assert body["meta"]["total"] == 0
    assert body["meta"]["has_next"] is False


def _codes(response: Response) -> set[str]:
    return {item["code"] for item in response.json()["items"]}
