"""INT-07 … INT-14 — команды подписки и изоляция комнат."""

import pytest

from tests.helpers.tickets_server import run_tickets_server
from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.integration
async def test_int07_subscribe_reply(base_url, subject, ticket_key):
    async with connect_ws(base_url, subject=subject) as client:
        reply = await client.subscribe("ticket", ticket_key)
        assert reply["type"] == "subscription.subscribed"
        assert reply["payload"] == {"topic": "ticket", "key": ticket_key}


@pytest.mark.integration
async def test_int08_unsubscribe_stops_delivery(base_url, subject, ticket_key, http):
    room = f"org:acme:ticket:{ticket_key}"

    async with connect_ws(base_url, subject=subject) as client:
        assert (await client.subscribe("ticket", ticket_key))["type"] == "subscription.subscribed"
        unsub = await client.unsubscribe("ticket", ticket_key)
        assert unsub["type"] == "subscription.unsubscribed"

        await http.post("/realtime/publish", params={"room": room, "type": "ticket.updated"})
        await client.expect_silence(timeout=0.5)


@pytest.mark.integration
async def test_int09_forbidden_subscription(redis_url):
    denied_key = unique_key("denied")
    async with run_tickets_server(
        {
            "REDIS_URL": redis_url,
            "REALTIME_BACKEND": "none",
            "DENIED_TICKETS": denied_key,
            "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "5",
            "WS_ADMISSION__LEASE_TTL": "PT8S",
        }
    ) as (url, _app):
        async with connect_ws(url, subject=unique_key("user")) as client:
            reply = await client.subscribe("ticket", denied_key)
            assert reply["type"] == "error"
            assert reply["payload"]["code"] == "forbidden"


@pytest.mark.integration
async def test_int10_room_isolation(base_url, http):
    key_a, key_b = unique_key("a"), unique_key("b")
    user_a, user_b = unique_key("ua"), unique_key("ub")

    async with (
        connect_ws(base_url, subject=user_a) as client_a,
        connect_ws(base_url, subject=user_b) as client_b,
    ):
        await client_a.subscribe("ticket", key_a)
        await client_b.subscribe("ticket", key_b)

        published = await http.post(
            "/realtime/publish",
            params={"room": f"org:acme:ticket:{key_a}", "type": "ticket.updated"},
            json={"marker": "only-a"},
        )
        event_id = published.json()["eventId"]

        event = await client_a.expect_event(event_type="ticket.updated")
        assert event["id"] == event_id
        await client_b.expect_silence(timeout=0.5)


@pytest.mark.integration
async def test_int11_resubscribe_no_duplicate_delivery(base_url, subject, ticket_key, http):
    room = f"org:acme:ticket:{ticket_key}"

    async with connect_ws(base_url, subject=subject) as client:
        assert (await client.subscribe("ticket", ticket_key))["type"] == "subscription.subscribed"
        assert (await client.subscribe("ticket", ticket_key))["type"] == "subscription.subscribed"

        published = await http.post("/realtime/publish", params={"room": room, "type": "ticket.updated"})
        event = await client.expect_event(event_type="ticket.updated")
        assert event["id"] == published.json()["eventId"]
        await client.expect_silence(timeout=0.4)


@pytest.mark.integration
async def test_int12_subscription_limit(base_url, subject):
    async with connect_ws(base_url, subject=subject) as client:
        for _ in range(3):
            reply = await client.subscribe("ticket", unique_key("k"))
            assert reply["type"] == "subscription.subscribed"

        overflow = await client.subscribe("ticket", unique_key("overflow"))
        assert overflow["type"] == "error"
        assert overflow["payload"]["code"] == "subscription_limit"
