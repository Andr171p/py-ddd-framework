import asyncio
from datetime import timedelta

import pytest
import websockets
from fastapi import status
from redis.asyncio import Redis

from ddf.application.limits import ConcurrencyPolicy
from ddf.infra.limits.concurrency.redis import RedisConcurrencyLimiter
from tests.helpers.tickets_server import run_tickets_server
from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.integration
async def test_int21_handshake_rate_limit(redis_url):
    async with run_tickets_server(
        {
            "REDIS_URL": redis_url,
            "REALTIME_BACKEND": "none",
            "WS_ADMISSION__CONNECT_LIMIT": "2",
            "WS_ADMISSION__CONNECT_WINDOW": "PT60S",
            "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "10",
            "WS_ADMISSION__LEASE_TTL": "PT8S",
        }
    ) as (url, _app):
        subject = unique_key("rl")
        clients = []
        for _ in range(2):
            ws = await websockets.connect(f"{url.replace('http', 'ws')}/ws?subject={subject}&org=acme")
            clients.append(ws)

        with pytest.raises(websockets.InvalidStatus) as exc:
            await websockets.connect(
                f"{url.replace('http', 'ws')}/ws?subject={subject}&org=acme",
                open_timeout=3,
            )
        assert exc.value.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        for ws in clients:
            await ws.close()


@pytest.mark.integration
@pytest.mark.xfail(reason="command_rate_policy не подключён в handle_subscription_commands", strict=False)
async def test_int22_command_rate_limit(base_url, subject, ticket_key):
    async with connect_ws(base_url, subject=subject) as client:
        for _ in range(200):
            await client.send_json(
                {
                    "id": str(__import__("uuid").uuid4()),
                    "type": "subscription.subscribe",
                    "payload": {"topic": "ticket", "key": ticket_key},
                }
            )
        with pytest.raises(websockets.ConnectionClosed) as exc:
            while True:
                await client.recv_json(timeout=2)
        assert exc.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.integration
async def test_int23_concurrency_limit(base_url):
    subject = unique_key("conc")
    opened = []

    for _ in range(3):
        ws = await websockets.connect(f"{base_url.replace('http', 'ws')}/ws?subject={subject}&org=acme")
        opened.append(ws)

    with pytest.raises(websockets.InvalidStatus) as exc:
        await websockets.connect(
            f"{base_url.replace('http', 'ws')}/ws?subject={subject}&org=acme",
            open_timeout=3,
        )
    assert exc.value.response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    for ws in opened:
        await ws.close()


@pytest.mark.integration
async def test_int24_lease_release_allows_reconnect(base_url):
    subject = unique_key("lease")

    async with connect_ws(base_url, subject=subject):
        pass

    await asyncio.sleep(0.2)

    async with connect_ws(base_url, subject=subject) as client:
        reply = await client.subscribe("ticket", unique_key("t"))
        assert reply["type"] == "subscription.subscribed"


@pytest.mark.integration
async def test_int27_subject_isolation_for_concurrency(base_url):
    user_a, user_b = unique_key("a"), unique_key("b")

    opened = [
        await websockets.connect(f"{base_url.replace('http', 'ws')}/ws?subject={user_a}&org=acme")
        for _ in range(3)
    ]

    async with connect_ws(base_url, subject=user_b) as other:
        reply = await other.subscribe("ticket", unique_key("t"))
        assert reply["type"] == "subscription.subscribed"

    for ws in opened:
        await ws.close()


@pytest.mark.integration
async def test_int28_lease_ttl_recovers_slot(redis_url):
    async with run_tickets_server(
        {
            "REDIS_URL": redis_url,
            "REALTIME_BACKEND": "none",
            "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "1",
            "WS_ADMISSION__LEASE_TTL": "PT4S",
            "WS_ADMISSION__CONNECT_LIMIT": "50",
        }
    ) as (url, _app):
        subject = unique_key("ttl")
        ws = await websockets.connect(f"{url.replace('http', 'ws')}/ws?subject={subject}&org=acme")
        await ws.close()
        await asyncio.sleep(0.1)

        redis = Redis.from_url(redis_url, decode_responses=True)
        limiter = RedisConcurrencyLimiter(redis, prefix="ddf:concurrency")
        lease = await limiter.acquire(
            f"ws:active:{subject}",
            ConcurrencyPolicy(limit=1, lease_ttl=timedelta(seconds=4)),
        )
        assert lease is not None
        await lease.release()
        await redis.aclose()
