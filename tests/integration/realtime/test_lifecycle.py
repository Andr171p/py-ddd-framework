"""INT-01 … INT-06 — lifecycle WebSocket-соединения."""

import pytest
import websockets
from starlette import status

from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.integration
async def test_int01_successful_connect(base_url, subject, tickets_runtime):
    async with connect_ws(base_url, subject=subject) as client:
        assert tickets_runtime["container"].connection_manager.count >= 1
        await client.ws.close()


@pytest.mark.integration
async def test_int02_normal_disconnect_releases_resources(base_url, subject, tickets_runtime, ticket_key):
    manager = tickets_runtime["container"].connection_manager

    async with connect_ws(base_url, subject=subject) as client:
        reply = await client.subscribe("ticket", ticket_key)
        assert reply["type"] == "subscription.subscribed"

    import asyncio

    await asyncio.sleep(0.2)
    assert manager.count == 0
    assert manager._rooms == {}


@pytest.mark.integration
async def test_int03_handler_exception_closes_1011(base_url, subject, monkeypatch):
    import tests.apps.realtime_tickets.app as tickets_app

    async def boom(_connection, *, resolve_room):
        raise RuntimeError("boom")

    monkeypatch.setattr(tickets_app, "handle_subscription_commands", boom)

    with pytest.raises((websockets.WebSocketException, TimeoutError, OSError)):
        async with connect_ws(base_url, subject=subject) as client:
            await client.recv_json(timeout=2.0)


@pytest.mark.integration
async def test_int04_shutdown_rejects_new_and_closes_existing(base_url, subject, tickets_runtime):
    manager = tickets_runtime["container"].connection_manager

    async with connect_ws(base_url, subject=subject) as client:
        manager.shutdown(code=status.WS_1001_GOING_AWAY)
        with pytest.raises((websockets.WebSocketException, TimeoutError, OSError)):
            await client.recv_json(timeout=3.0)

    other = unique_key("user")
    with pytest.raises((websockets.WebSocketException, TimeoutError, OSError)):
        async with connect_ws(base_url, subject=other, open_timeout=2.0):
            pass
