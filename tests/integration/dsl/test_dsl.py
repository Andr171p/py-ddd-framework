"""Exercise DSL requests from JSON through FastAPI and SQLite."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

pytest.importorskip("sqlalchemy", reason="Install the sqlalchemy extra for DSL integration tests")

from tests.integration.dsl.app import make_app


@pytest.fixture
def client():
    app, engine = make_app()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        engine.dispose()


TICKETS = {
    1: {"id": 1, "title": "Printer offline", "status": "open", "priority": 3, "assigneeName": "Ada"},
    2: {"id": 2, "title": "Paper jam", "status": "pending", "priority": 2, "assigneeName": None},
    3: {"id": 3, "title": "PRINTER fixed", "status": "closed", "priority": 1, "assigneeName": "Bob"},
    4: {"id": 4, "title": "New monitor", "status": "open", "priority": 2, "assigneeName": None},
}


@pytest.mark.parametrize(
    ("expression", "ids"),
    [
        ({"field": "status", "op": "$eq", "value": "open"}, [1, 4]),
        ({"field": "status", "op": "$ne", "value": "closed"}, [1, 2, 4]),
        ({"field": "priority", "op": "$gt", "value": 2}, [1]),
        ({"field": "priority", "op": "$gte", "value": 2}, [1, 2, 4]),
        ({"field": "priority", "op": "$lt", "value": 2}, [3]),
        ({"field": "priority", "op": "$lte", "value": 2}, [2, 3, 4]),
        ({"field": "status", "op": "$in", "value": ["open", "pending"]}, [1, 2, 4]),
        ({"field": "status", "op": "$nin", "value": ["open", "pending"]}, [3]),
        ({"field": "status", "op": "$in", "value": []}, []),
        ({"field": "status", "op": "$nin", "value": []}, [1, 2, 3, 4]),
        ({"field": "title", "op": "$like", "value": "%jam%"}, [2]),
        ({"field": "title", "op": "$ilike", "value": "%printer%"}, [1, 3]),
        ({"field": "assigneeName", "op": "$isNull"}, [2, 4]),
        ({"field": "assigneeName", "op": "$isNotNull"}, [1, 3]),
        ({"field": "assigneeName", "op": "$eq", "value": "Ada"}, [1]),
        ({"field": "status", "op": "$eq", "value": "cancelled"}, []),
    ],
    ids=[
        "open",
        "not-closed",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not-in",
        "empty-in",
        "empty-not-in",
        "like",
        "ilike",
        "unassigned",
        "assigned",
        "camel-case",
        "no-results",
    ],
)
def test_filter_returns_matching_tickets(client, expression, ids):
    response = client.post("/tickets/search", json=expression)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [TICKETS[id_] for id_ in ids]


def test_find_open_or_printer_tickets_excluding_low_priority(client):
    response = client.post(
        "/tickets/search",
        json={
            "op": "$and",
            "filters": [
                {
                    "op": "$or",
                    "filters": [
                        {"field": "status", "op": "$eq", "value": "open"},
                        {"query": "printer"},
                    ],
                },
                {"filter": {"field": "priority", "op": "$lt", "value": 2}},
            ],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [TICKETS[1], TICKETS[4]]


def test_exclude_open_and_pending_tickets(client):
    response = client.post(
        "/tickets/search",
        json={
            "filter": {
                "op": "$or",
                "filters": [
                    {"field": "status", "op": "$eq", "value": "open"},
                    {"field": "status", "op": "$eq", "value": "pending"},
                ],
            }
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [TICKETS[3]]


@pytest.mark.parametrize(
    "expression",
    [
        {"field": "internalNote", "op": "$eq", "value": "a"},
        {"field": "missing", "op": "$eq", "value": 1},
        {"field": "priority", "op": "$in", "value": 2},
        {"field": "title", "op": "$like", "value": 2},
        {"op": "$and", "filters": []},
        {"field": "status", "op": "$unknown", "value": "open"},
        {"field": "status", "value": "open"},
    ],
    ids=[
        "private-field",
        "unknown-field",
        "in-needs-list",
        "like-needs-string",
        "empty-group",
        "unknown-operator",
        "missing-operator",
    ],
)
def test_invalid_filter_returns_422(client, expression):
    response = client.post("/tickets/search", json=expression)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
