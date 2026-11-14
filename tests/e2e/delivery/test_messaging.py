"""E2E-01…04, E2E-07 — cross-instance доставка и изоляция."""

import pytest
from httpx import AsyncClient

from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.e2e
async def test_e2e01_cross_instance_delivery(url_a, url_b):
    subject, key = unique_key("u"), unique_key("t")
    room = f"org:acme:ticket:{key}"

    async with connect_ws(url_a, subject=subject) as client:
        assert (await client.subscribe("ticket", key))["type"] == "subscription.subscribed"

        async with AsyncClient(base_url=url_b, timeout=5.0, trust_env=False) as http:
            published = await http.post(
                "/realtime/publish",
                params={"room": room, "type": "ticket.updated"},
                json={"from": "b"},
            )

        event = await client.expect_event(event_type="ticket.updated", timeout=8.0)
        assert event["id"] == published.json()["eventId"]
        assert event["payload"]["from"] == "b"


@pytest.mark.e2e
async def test_e2e02_multi_instance_fanout(url_a, url_b):
    key = unique_key("fan")
    room = f"org:acme:ticket:{key}"
    user_a, user_b = unique_key("a"), unique_key("b")

    async with (
        connect_ws(url_a, subject=user_a) as client_a,
        connect_ws(url_b, subject=user_b) as client_b,
    ):
        assert (await client_a.subscribe("ticket", key))["type"] == "subscription.subscribed"
        assert (await client_b.subscribe("ticket", key))["type"] == "subscription.subscribed"

        async with AsyncClient(base_url=url_a, timeout=5.0, trust_env=False) as http:
            published = await http.post(
                "/realtime/publish",
                params={"room": room, "type": "ticket.updated"},
                json={"fanout": True},
            )
        event_id = published.json()["eventId"]

        event_a = await client_a.expect_event(event_type="ticket.updated", timeout=8.0)
        event_b = await client_b.expect_event(event_type="ticket.updated", timeout=8.0)
        assert event_a["id"] == event_id
        assert event_b["id"] == event_id
        await client_a.expect_silence(timeout=0.4)
        await client_b.expect_silence(timeout=0.4)


@pytest.mark.e2e
async def test_e2e03_room_isolation_across_instances(url_a, url_b):
    key_a, key_b = unique_key("ra"), unique_key("rb")
    user_a, user_b = unique_key("ua"), unique_key("ub")

    async with (
        connect_ws(url_a, subject=user_a) as client_a,
        connect_ws(url_b, subject=user_b) as client_b,
    ):
        await client_a.subscribe("ticket", key_a)
        await client_b.subscribe("ticket", key_b)

        async with AsyncClient(base_url=url_b, timeout=5.0, trust_env=False) as http:
            await http.post(
                "/realtime/publish",
                params={"room": f"org:acme:ticket:{key_a}", "type": "ticket.updated"},
                json={"only": "a"},
            )

        event = await client_a.expect_event(event_type="ticket.updated", timeout=8.0)
        assert event["payload"]["only"] == "a"
        await client_b.expect_silence(timeout=0.5)


@pytest.mark.e2e
async def test_e2e04_cross_organization_isolation(url_a, url_b):
    key = unique_key("shared-id")
    user_a, user_b = unique_key("oa"), unique_key("ob")

    async with (
        connect_ws(url_a, subject=user_a, org="acme") as client_a,
        connect_ws(url_b, subject=user_b, org="globex") as client_b,
    ):
        await client_a.subscribe("ticket", key)
        await client_b.subscribe("ticket", key)

        async with AsyncClient(base_url=url_a, timeout=5.0, trust_env=False) as http:
            await http.post(
                "/realtime/publish",
                params={"room": f"org:acme:ticket:{key}", "type": "ticket.updated"},
                json={"org": "acme"},
            )

        event = await client_a.expect_event(event_type="ticket.updated", timeout=8.0)
        assert event["payload"]["org"] == "acme"
        await client_b.expect_silence(timeout=0.5)


@pytest.mark.e2e
async def test_e2e07_unsubscribe_stops_cross_instance_delivery(url_a, url_b):
    key = unique_key("unsub")
    room = f"org:acme:ticket:{key}"
    subject = unique_key("u")

    async with connect_ws(url_a, subject=subject) as client:
        await client.subscribe("ticket", key)
        unsub = await client.unsubscribe("ticket", key)
        assert unsub["type"] == "subscription.unsubscribed"

        async with AsyncClient(base_url=url_b, timeout=5.0, trust_env=False) as http:
            await http.post("/realtime/publish", params={"room": room, "type": "ticket.updated"})

        await client.expect_silence(timeout=0.8)
