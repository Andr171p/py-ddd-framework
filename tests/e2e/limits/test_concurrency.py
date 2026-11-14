"""E2E-08, E2E-11, E2E-12 — распределённые concurrency limits."""

import asyncio

import pytest
import websockets
from fastapi import status

from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.e2e
async def test_e2e08_global_concurrency_across_instances(url_a, url_b):
    subject = unique_key("conc")
    ws_a = await websockets.connect(f"{url_a.replace('http', 'ws')}/ws?subject={subject}&org=acme")
    ws_b = await websockets.connect(f"{url_b.replace('http', 'ws')}/ws?subject={subject}&org=acme")

    with pytest.raises(websockets.InvalidStatus) as exc:
        await websockets.connect(
            f"{url_a.replace('http', 'ws')}/ws?subject={subject}&org=acme",
            open_timeout=3,
        )
    assert exc.value.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    await ws_a.close()
    await ws_b.close()


@pytest.mark.e2e
async def test_e2e11_release_across_instances(url_a, url_b):
    subject = unique_key("move")

    async with connect_ws(url_a, subject=subject):
        pass

    await asyncio.sleep(0.3)

    async with connect_ws(url_b, subject=subject) as client:
        reply = await client.subscribe("ticket", unique_key("t"))
        assert reply["type"] == "subscription.subscribed"


@pytest.mark.e2e
async def test_e2e12_subject_isolation(url_a, url_b):
    noisy = unique_key("noisy")
    other = unique_key("other")

    opened = [
        await websockets.connect(f"{url.replace('http', 'ws')}/ws?subject={noisy}&org=acme")
        for url in (url_a, url_b)
    ]

    async with connect_ws(url_a, subject=other) as client:
        reply = await client.subscribe("ticket", unique_key("t"))
        assert reply["type"] == "subscription.subscribed"

    for ws in opened:
        await ws.close()
