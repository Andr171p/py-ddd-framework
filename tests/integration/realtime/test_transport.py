"""INT-15 … INT-20 — валидация и безопасность транспорта."""

import asyncio
import json
from uuid import uuid4

import pytest
import websockets
from starlette import status

from tests.helpers.ws_client import connect_ws, unique_key


@pytest.mark.integration
async def test_int15_binary_frame_closes_1003(base_url, subject):
    ws_url = base_url.replace("http://", "ws://") + f"/ws?subject={subject}&org=acme"
    async with websockets.connect(ws_url, open_timeout=5) as ws:
        await ws.send(b"\x00\x01")
        with pytest.raises(websockets.ConnectionClosed) as exc:
            await asyncio.wait_for(ws.recv(), timeout=3)
        assert exc.value.code == status.WS_1003_UNSUPPORTED_DATA


@pytest.mark.integration
async def test_int16_message_too_big_closes_1009(base_url, subject):
    # max_incoming_bytes=256 в conftest
    ws_url = base_url.replace("http://", "ws://") + f"/ws?subject={subject}&org=acme"
    async with websockets.connect(ws_url, open_timeout=5) as ws:
        await ws.send("x" * 512)
        with pytest.raises(websockets.ConnectionClosed) as exc:
            await asyncio.wait_for(ws.recv(), timeout=3)
        assert exc.value.code == status.WS_1009_MESSAGE_TOO_BIG


@pytest.mark.integration
async def test_int17_size_boundary(base_url, subject):
    ws_url = base_url.replace("http://", "ws://") + f"/ws?subject={subject}&org=acme"
    # ровно на лимите — валидный JSON короче; проверяем 1 байт сверх лимита
    async with websockets.connect(ws_url, open_timeout=5) as ws:
        await ws.send("y" * 257)
        with pytest.raises(websockets.ConnectionClosed) as exc:
            await asyncio.wait_for(ws.recv(), timeout=3)
        assert exc.value.code == status.WS_1009_MESSAGE_TOO_BIG


@pytest.mark.integration
async def test_int18_invalid_commands_counter_and_reset(base_url, subject, ticket_key):
    async with connect_ws(base_url, subject=subject) as client:
        for _ in range(4):
            await client.send_json({"nope": True})
            error = await client.recv_json()
            assert error["type"] == "error"
            assert error["payload"]["code"] == "invalid_command"

        # валидная команда сбрасывает счётчик
        reply = await client.subscribe("ticket", ticket_key)
        assert reply["type"] == "subscription.subscribed"

        for _ in range(4):
            await client.send_json({"still": "bad"})
            await client.recv_json()

        await client.send_json({"still": "bad"})
        with pytest.raises(websockets.ConnectionClosed) as exc:
            await client.recv_json(timeout=3)
        assert exc.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.integration
async def test_int19_admission_requires_subject(base_url):
    ws_url = base_url.replace("http://", "ws://") + "/ws?org=acme"
    with pytest.raises(Exception):
        async with websockets.connect(ws_url, open_timeout=3):
            pass
