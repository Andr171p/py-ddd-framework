from typing import Any

import asyncio
import importlib
import os
import socket
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import uvicorn

from tests.helpers.ws_client import wait_ready

APP_MODULE = "tests.apps.realtime_tickets.app"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _reload_app(env: Mapping[str, str]):
    for key, value in env.items():
        os.environ[key] = value

    for name in list(sys.modules):
        if name == "tests.apps.realtime_tickets" or name.startswith("tests.apps.realtime_tickets."):
            del sys.modules[name]

    module = importlib.import_module(APP_MODULE)
    return module.app


@asynccontextmanager
async def run_tickets_server(env: Mapping[str, str]) -> AsyncIterator[tuple[str, Any]]:
    app = _reload_app(env)
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    task = asyncio.create_task(server.serve(), name="tickets-uvicorn")
    base_url = f"http://127.0.0.1:{port}"

    try:
        deadline = asyncio.get_running_loop().time() + 30
        while not server.started:
            if task.done():
                raise RuntimeError(f"uvicorn failed to start: {task.exception()!r}")
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("uvicorn did not start")
            await asyncio.sleep(0.05)
        await wait_ready(base_url, timeout=30.0)
        yield base_url, app
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10.0)
