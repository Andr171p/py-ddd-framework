"""INT-29 … INT-34 — Redis/Rabbit publish → consumer → local emit."""

import asyncio
import os

import pytest
from fastapi import status
from httpx import AsyncClient
from testcontainers.community.rabbitmq import RabbitMqContainer
from testcontainers.community.redis import RedisContainer

from tests.helpers.tickets_server import run_tickets_server
from tests.helpers.ws_client import connect_ws, unique_key

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="module")
def broker_redis_url() -> str:
    with RedisContainer("redis:7-alpine") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest.fixture(scope="module")
def rabbit_url() -> str:
    with RabbitMqContainer(os.getenv("RABBITMQ_IMAGE", "rabbitmq:4.3-management-alpine")) as rabbit:
        params = rabbit.get_connection_params()
        yield f"amqp://{params.credentials.username}:{params.credentials.password}@{params.host}:{params.port}/"


@pytest.mark.integration
async def test_int29_redis_publish_consume(broker_redis_url):
    subject, key = unique_key("u"), unique_key("t")
    room = f"org:acme:ticket:{key}"

    async with (
        run_tickets_server(
            {
                "REDIS_URL": broker_redis_url,
                "REALTIME_BACKEND": "redis",
                "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "5",
                "WS_ADMISSION__LEASE_TTL": "PT10S",
            }
        ) as (url, _app),
        connect_ws(url, subject=subject) as client,
    ):
        assert (await client.subscribe("ticket", key))["type"] == "subscription.subscribed"
        async with AsyncClient(base_url=url, timeout=5.0, trust_env=False) as http:
            published = await http.post(
                "/realtime/publish",
                params={"room": room, "type": "ticket.updated"},
                json={"via": "redis"},
            )
        event = await client.expect_event(event_type="ticket.updated", timeout=5.0)
        assert event["id"] == published.json()["eventId"]
        assert event["payload"]["via"] == "redis"


@pytest.mark.integration
async def test_int30_rabbit_publish_consume(broker_redis_url, rabbit_url):
    subject, key = unique_key("u"), unique_key("t")
    room = f"org:acme:ticket:{key}"

    async with (
        run_tickets_server(
            {
                "REDIS_URL": broker_redis_url,
                "RABBIT_URL": rabbit_url,
                "REALTIME_BACKEND": "rabbit",
                "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "5",
                "WS_ADMISSION__LEASE_TTL": "PT10S",
            }
        ) as (url, _app),
        connect_ws(url, subject=subject) as client,
    ):
        assert (await client.subscribe("ticket", key))["type"] == "subscription.subscribed"
        await asyncio.sleep(0.5)
        async with AsyncClient(base_url=url, timeout=5.0, trust_env=False) as http:
            published = await http.post(
                "/realtime/publish",
                params={"room": room, "type": "ticket.updated"},
                json={"via": "rabbit"},
            )
        event = await client.expect_event(event_type="ticket.updated", timeout=8.0)
        assert event["id"] == published.json()["eventId"]
        assert event["payload"]["via"] == "rabbit"


@pytest.mark.integration
async def test_int31_broadcast_to_local_subscribers(base_url, http):
    key = unique_key("fan")
    room = f"org:acme:ticket:{key}"
    users = [unique_key("u") for _ in range(3)]

    async with (
        connect_ws(base_url, subject=users[0]) as c0,
        connect_ws(base_url, subject=users[1]) as c1,
        connect_ws(base_url, subject=users[2]) as c2,
    ):
        for client in (c0, c1, c2):
            assert (await client.subscribe("ticket", key))["type"] == "subscription.subscribed"

        published = await http.post("/realtime/publish", params={"room": room, "type": "ticket.updated"})
        event_id = published.json()["eventId"]

        for client in (c0, c1, c2):
            event = await client.expect_event(event_type="ticket.updated")
            assert event["id"] == event_id


@pytest.mark.integration
async def test_int34_no_local_subscribers_is_ok(base_url, http, tickets_runtime):
    room = f"org:acme:ticket:{unique_key('empty')}"
    response = await http.post("/realtime/publish", params={"room": room, "type": "ticket.updated"})
    assert response.status_code == status.HTTP_200_OK
    assert tickets_runtime["container"].connection_manager.count == 0
