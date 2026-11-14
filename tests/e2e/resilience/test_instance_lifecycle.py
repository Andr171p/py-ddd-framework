"""E2E-14, E2E-15 — shutdown / crash worker."""

import asyncio
import contextlib

import pytest
import websockets

from tests.e2e.harness import compose
from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.e2e
@pytest.mark.destructive
async def test_e2e14_graceful_shutdown_instance_a(url_a, url_b):
    subject = unique_key("shut")
    async with connect_ws(url_a, subject=subject) as client_a:
        await client_a.subscribe("ticket", unique_key("t"))
        compose(["stop", "ws-a"])
        with pytest.raises(Exception):  # noqa: B017
            await client_a.recv_json(timeout=10.0)

    async with connect_ws(url_b, subject=unique_key("alive")) as client_b:
        reply = await client_b.subscribe("ticket", unique_key("t"))
        assert reply["type"] == "subscription.subscribed"


@pytest.mark.e2e
@pytest.mark.destructive
async def test_e2e15_worker_crash_releases_lease_after_ttl(url_a, url_b):
    subject = unique_key("crash")
    ws = await websockets.connect(f"{url_a.replace('http', 'ws')}/ws?subject={subject}&org=acme")
    try:
        compose(["kill", "ws-a"])
        # lease_ttl=PT4S в docker compose
        await asyncio.sleep(5)

        async with connect_ws(url_b, subject=subject) as client:
            reply = await client.subscribe("ticket", unique_key("t"))
            assert reply["type"] == "subscription.subscribed"
    finally:
        with contextlib.suppress(Exception):
            await ws.close()
