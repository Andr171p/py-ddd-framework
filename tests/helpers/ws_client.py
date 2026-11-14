from typing import Any

import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import websockets
from fastapi import status
from websockets.asyncio.client import ClientConnection


class WsTestClient:
    """Тонкий клиент для realtime-протокола с таймаутами на каждый recv."""

    def __init__(self, ws: ClientConnection, *, default_timeout: float = 5.0) -> None:
        self.ws = ws
        self.default_timeout = default_timeout

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(payload))

    async def recv_json(self, *, timeout: float | None = None) -> dict[str, Any]:
        raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout or self.default_timeout)
        if isinstance(raw, bytes):
            raise AssertionError("expected text frame, got binary")
        return json.loads(raw)

    async def subscribe(self, topic: str, key: str, *, timeout: float | None = None) -> dict[str, Any]:
        command_id = str(uuid4())
        await self.send_json(
            {
                "id": command_id,
                "type": "subscription.subscribe",
                "payload": {"topic": topic, "key": key},
            }
        )
        reply = await self.recv_json(timeout=timeout)
        assert reply.get("replyTo") == command_id or reply.get("type") == "error"
        return reply

    async def unsubscribe(self, topic: str, key: str, *, timeout: float | None = None) -> dict[str, Any]:
        command_id = str(uuid4())
        await self.send_json(
            {
                "id": command_id,
                "type": "subscription.unsubscribe",
                "payload": {"topic": topic, "key": key},
            }
        )
        return await self.recv_json(timeout=timeout)

    async def expect_event(
        self,
        *,
        event_type: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        message = await self.recv_json(timeout=timeout)
        if event_type is not None:
            assert message.get("type") == event_type, message
        return message

    async def expect_silence(self, *, timeout: float = 0.5) -> None:
        try:
            message = await self.recv_json(timeout=timeout)
        except TimeoutError:
            return
        raise AssertionError(f"unexpected message: {message}")


@asynccontextmanager
async def connect_ws(
    base_url: str,
    *,
    subject: str,
    org: str = "acme",
    open_timeout: float = 5.0,
    default_timeout: float = 5.0,
):
    http_base = base_url.rstrip("/")
    ws_base = http_base.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/ws?subject={subject}&org={org}"

    async with websockets.connect(uri, open_timeout=open_timeout) as ws:
        yield WsTestClient(ws, default_timeout=default_timeout)


async def wait_ready(base_url: str, *, timeout: float = 30.0, interval: float = 0.25) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    async with httpx.AsyncClient(trust_env=False) as client:
        while True:
            try:
                response = await client.get(f"{base_url.rstrip('/')}/ready", timeout=2.0)
                if response.status_code == status.HTTP_200_OK:
                    return
            except httpx.HTTPError:
                pass

            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"service not ready: {base_url}")
            await asyncio.sleep(interval)


def unique_key(prefix: str = "t") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"
