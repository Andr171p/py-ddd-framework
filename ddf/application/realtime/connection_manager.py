from typing import Any

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from fastapi import status

from .connection import Connection
from .exceptions import TooManySubscriptionsError
from .messages import Event, Subscription
from .types import Room


class ConnectionManager:
    def __init__(self, *, max_subscriptions: int = 64, max_message_bytes: int = 65_536) -> None:
        if max_subscriptions < 1 or max_message_bytes < 1:
            raise ValueError("Limits must be positive")

        self.max_subscriptions = max_subscriptions
        self.max_message_bytes = max_message_bytes

        self._closing = False

        self._connections: dict[UUID, Connection] = {}
        self._rooms: dict[Room, set[UUID]] = defaultdict(set)
        self._memberships: dict[UUID, set[Room]] = {}
        self._pinned: dict[UUID, set[Room]] = {}
        self._subscriptions: dict[UUID, dict[Subscription, Room]] = {}

    @property
    def closing(self) -> bool:
        return self._closing

    @property
    def count(self) -> int:
        return len(self._connections)

    @contextmanager
    def connect(self, connection: Connection) -> Iterator[Connection]:
        if self._closing:
            raise RuntimeError("ConnectionManager is shutting down")

        if connection.id in self._connections:
            raise ValueError(f"Connection id={connection.id!r} already connected")

        self._connections[connection.id] = connection
        self._memberships[connection.id] = set()
        self._pinned[connection.id] = set()
        self._subscriptions[connection.id] = {}

        try:
            yield connection
        finally:
            self.disconnect(connection)

    def disconnect(self, connection: Connection) -> None:
        if self._connections.get(connection.id) is not connection:
            return

        connection.mark_closed()

        for room in tuple(self._memberships[connection.id]):
            self._detach(connection, room)

        for store in (self._memberships, self._pinned, self._subscriptions, self._connections):
            del store[connection.id]

    def join(self, connection: Connection, room: Room) -> None:
        self._require(connection)

        self._pinned[connection.id].add(room)
        self._attach(connection, room)

    def leave(self, connection: Connection, room: Room) -> None:
        self._require(connection)

        self._pinned[connection.id].discard(room)
        self._release_if_unused(connection, room)

    def subscribe(self, connection: Connection, subscription: Subscription, room: Room) -> None:
        self._require(connection)

        conn_subscriptions = self._subscriptions[connection.id]
        previous = conn_subscriptions.get(subscription)

        if previous is None and len(conn_subscriptions) >= self.max_subscriptions:
            raise TooManySubscriptionsError()

        conn_subscriptions[subscription] = room
        self._attach(connection, room)

        if previous is not None and previous != room:
            self._release_if_unused(connection, previous)

    def unsubscribe(self, connection: Connection, subscription: Subscription) -> None:
        self._require(connection)

        room = self._subscriptions[connection.id].pop(subscription, None)

        if room is not None:
            self._release_if_unused(connection, room)

    def emit(self, event: Event[Any], *, to: Room) -> None:
        payload = event.model_dump_json(by_alias=True, exclude_none=True)

        if len(payload.encode("utf-8")) > self.max_message_bytes:
            raise ValueError("Serialized realtime event is too large")

        for cid in tuple(self._rooms.get(to, ())):
            if (connection := self._connections.get(cid)) is not None:
                connection.offer(payload)

    def shutdown(self, code: int = status.WS_1001_GOING_AWAY) -> None:
        self._closing = True

        for connection in tuple(self._connections.values()):
            connection.request_close(code)

    def _require(self, connection: Connection) -> None:
        if self._connections.get(connection.id) is not connection or connection.closed:
            raise RuntimeError("Connection is not active")

    def _attach(self, connection: Connection, room: Room) -> None:
        self._memberships[connection.id].add(room)
        self._rooms[room].add(connection.id)

    def _detach(self, connection: Connection, room: Room) -> None:
        self._memberships[connection.id].discard(room)

        if (members := self._rooms.get(room)) is not None:
            members.discard(connection.id)

            if not members:
                del self._rooms[room]

    def _release_if_unused(self, connection: Connection, room: Room) -> None:
        pinned = room in self._pinned[connection.id]
        subscribed = room in self._subscriptions[connection.id].values()

        if not pinned and not subscribed:
            self._detach(connection, room)
