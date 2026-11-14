"""E2E-22 — HTTP обновление заявки → realtime клиентам."""

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.e2e
async def test_e2e22_ticket_update_notifies_subscribers(url_a, url_b):
    ticket_id = unique_key("ticket")
    user_a, user_b, stranger = unique_key("a"), unique_key("b"), unique_key("s")

    async with (
        connect_ws(url_a, subject=user_a, org="acme") as client_a,
        connect_ws(url_b, subject=user_b, org="acme") as client_b,
        connect_ws(url_b, subject=stranger, org="globex") as outsider,
    ):
        assert (await client_a.subscribe("ticket", ticket_id))["type"] == "subscription.subscribed"
        assert (await client_b.subscribe("ticket", ticket_id))["type"] == "subscription.subscribed"
        assert (await outsider.subscribe("ticket", ticket_id))["type"] == "subscription.subscribed"

        async with AsyncClient(base_url=url_a, timeout=5.0, trust_env=False) as http:
            response = await http.post(
                f"/tickets/{ticket_id}/status",
                json={"status": "resolved", "org_id": "acme"},
            )
        assert response.status_code == status.HTTP_200_OK
        event_id = response.json()["eventId"]

        for client in (client_a, client_b):
            event = await client.expect_event(event_type="ticket.updated", timeout=8.0)
            assert event["id"] == event_id
            assert event["payload"]["status"] == "resolved"

        await outsider.expect_silence(timeout=0.6)
