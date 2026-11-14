"""Общие helpers для E2E: compose и readiness без pytest-зависимостей."""

from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import status

COMPOSE_FILE = Path(__file__).resolve().parent / "docker" / "compose.yaml"
WS_A = os.getenv("E2E_WS_A", "http://127.0.0.1:18001")
WS_B = os.getenv("E2E_WS_B", "http://127.0.0.1:18002")

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def compose(args: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=True,
        env=env,
    )


def wait_http(url: str, *, timeout: float = 90.0, interval: float = 0.15) -> None:
    deadline = time.monotonic() + timeout
    ready = f"{url.rstrip('/')}/ready"
    while time.monotonic() < deadline:
        try:
            with _opener.open(ready, timeout=1.5) as response:
                if response.status == status.HTTP_200_OK:
                    return
        except (urllib.error.URLError, TimeoutError, OSError, ConnectionError):
            pass
        time.sleep(interval)
    raise TimeoutError(f"not ready: {url}")


def ensure_instances(*, recreate: tuple[str, ...] = ()) -> None:
    if recreate:
        compose(["up", "-d", "--wait", *recreate])
    wait_http(WS_A)
    wait_http(WS_B)


def stack_up(*, build: bool | None = None) -> None:
    env = os.environ.copy()
    env.setdefault("REALTIME_BACKEND", "redis")
    args = ["up", "-d", "--wait"]
    if build is None:
        build = os.getenv("E2E_BUILD", "0") == "1"
    if build:
        args.insert(1, "--build")
    compose(args, env=env)
    ensure_instances()


def stack_down() -> None:
    compose(["down", "-v"])
