from typing import NewType, Protocol

from collections.abc import Awaitable, Callable

from .messages import Event, Subscription

# Внутренний адрес группы соединений
Room = NewType("Room", str)

type RoomResolver = Callable[[Subscription], Awaitable[Room]]


class RealtimePublisher[T](Protocol):
    async def __call__(self, event: Event[T], *, to: Room) -> None: ...


__all__ = ["RealtimePublisher", "Room", "RoomResolver"]
