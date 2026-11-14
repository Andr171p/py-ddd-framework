from typing import Any

import os
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from testcontainers.community.redis import RedisContainer

from tests.helpers.tickets_server import run_tickets_server
from tests.helpers.ws_client import unique_key

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_DEFAULT_ENV = {
    "REALTIME_BACKEND": "none",
    "MAX_SUBSCRIPTIONS": "3",
    "WS_ADMISSION__CONNECT_LIMIT": "50",
    "WS_ADMISSION__CONNECT_WINDOW": "PT60S",
    "WS_ADMISSION__MAX_CONCURRENT_CONNECTIONS": "3",
    "WS_ADMISSION__LEASE_TTL": "PT8S",
    "WS_SUBSCRIPTION__AUTHORIZATION_TIMEOUT": "1",
    "WS_MAX_INCOMING_BYTES": "256",
}


@pytest.fixture(scope="session")
def redis_url() -> str:
    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
async def tickets_server(redis_url: str) -> AsyncIterator[tuple[str, Any]]:
    async with run_tickets_server(
        {
            **_DEFAULT_ENV,
            "REDIS_URL": redis_url,
            "INSTANCE_NAME": f"int-{unique_key('app')}",
        }
    ) as server:
        yield server


@pytest.fixture
def base_url(tickets_server) -> str:
    return tickets_server[0]


@pytest.fixture
def tickets_app(tickets_server):
    return tickets_server[1]


@pytest.fixture
def tickets_runtime(tickets_app) -> dict[str, Any]:
    return tickets_app.state.runtime


@pytest.fixture
async def http(base_url: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url=base_url, timeout=5.0, trust_env=False) as client:
        yield client


@pytest.fixture
def subject() -> str:
    return unique_key("user")


@pytest.fixture
def ticket_key() -> str:
    return unique_key("ticket")
