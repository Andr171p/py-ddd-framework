"""Locust scenarios for DDF realtime (LOAD-01, LOAD-05, LOAD-06)."""

from __future__ import annotations

import json
import os
import time
from uuid import uuid4

import websocket
from locust import HttpUser, between, events, task
from locust.runners import MasterRunner

ROOM_PREFIX = "org:acme:ticket:"


class RealtimeUser(HttpUser):
    wait_time = between(0.2, 1.0)
    ticket_key: str

    def on_start(self) -> None:
        self.ticket_key = f"load-{uuid4().hex[:8]}"
        self.subject = f"user-{uuid4().hex[:8]}"
        self.ws = None
        self._connect_and_subscribe()

    def _ws_url(self) -> str:
        base = self.host.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/ws?subject={self.subject}&org=acme"

    def _connect_and_subscribe(self) -> None:
        start = time.perf_counter()
        try:
            self.ws = websocket.create_connection(self._ws_url(), timeout=5)
            command_id = str(uuid4())
            self.ws.send(
                json.dumps(
                    {
                        "id": command_id,
                        "type": "subscription.subscribe",
                        "payload": {"topic": "ticket", "key": self.ticket_key},
                    }
                )
            )
            reply = json.loads(self.ws.recv())
            elapsed = (time.perf_counter() - start) * 1000
            ok = reply.get("type") == "subscription.subscribed"
            events.request.fire(
                request_type="WS",
                name="handshake+subscribe",
                response_time=elapsed,
                response_length=len(json.dumps(reply)),
                exception=None if ok else Exception(reply),
                context={},
            )
        except Exception as exc:
            events.request.fire(
                request_type="WS",
                name="handshake+subscribe",
                response_time=(time.perf_counter() - start) * 1000,
                response_length=0,
                exception=exc,
                context={},
            )
            self.ws = None

    @task(3)
    def publish_and_receive(self) -> None:
        if self.ws is None:
            self._connect_and_subscribe()
            if self.ws is None:
                return

        room = f"{ROOM_PREFIX}{self.ticket_key}"
        start = time.perf_counter()
        with self.client.post(
            "/realtime/publish",
            params={"room": room, "type": "ticket.updated"},
            json={"ts": start},
            name="POST /realtime/publish",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
                return
            event_id = response.json()["eventId"]

        try:
            self.ws.settimeout(5)
            while True:
                raw = self.ws.recv()
                message = json.loads(raw)
                if message.get("id") == event_id:
                    break
            events.request.fire(
                request_type="WS",
                name="delivery",
                response_time=(time.perf_counter() - start) * 1000,
                response_length=len(raw),
                exception=None,
                context={},
            )
        except Exception as exc:
            events.request.fire(
                request_type="WS",
                name="delivery",
                response_time=(time.perf_counter() - start) * 1000,
                response_length=0,
                exception=exc,
                context={},
            )

    @task(1)
    def churn_reconnect(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.subject = f"user-{uuid4().hex[:8]}"
        self._connect_and_subscribe()

    def on_stop(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass


@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    if isinstance(environment.runner, MasterRunner):
        return
    # host can be overridden: locust -f ... --host http://127.0.0.1:18001
    if environment.host is None:
        environment.host = os.getenv("LOAD_HOST", "http://127.0.0.1:18001")
