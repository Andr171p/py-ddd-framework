import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient

COMPOSE_FILE = Path(__file__).resolve().parent / "docker" / "compose.yaml"
BASE_URL = os.getenv("DSL_E2E_BASE_URL", "http://127.0.0.1:18121")
READY_TIMEOUT_SECONDS = 90.0
COMPOSE_LOG_TAIL = 4000
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    root = str(Path(__file__).resolve().parent)
    for item in items:
        if str(item.path).startswith(root):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def api_url() -> Iterator[str]:
    if os.getenv("DSL_E2E_BASE_URL"):
        wait_health(BASE_URL)
        yield BASE_URL
        return

    if os.getenv("DSL_E2E_MANAGE", "1") == "1":
        _compose_up()

    try:
        wait_health(BASE_URL)
        yield BASE_URL
    finally:
        if os.getenv("DSL_E2E_MANAGE", "1") == "1" and os.getenv("DSL_E2E_KEEP", "0") != "1":
            subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"], check=False)


@pytest.fixture
async def client(api_url: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(base_url=api_url, timeout=30.0, trust_env=False) as http:
        yield http


def wait_health(url: str) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    target = f"{url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            with _OPENER.open(target, timeout=2) as response:
                if response.status == status.HTTP_200_OK:
                    return
        except (urllib.error.URLError, TimeoutError, OSError, ConnectionError):
            time.sleep(0.2)
    raise TimeoutError(target)


def _compose_up() -> None:
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"]
    if os.getenv("DSL_E2E_BUILD", "1") != "0":
        command.append("--build")
    command.append("--wait")
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout)[-COMPOSE_LOG_TAIL:]
        raise RuntimeError(details)
