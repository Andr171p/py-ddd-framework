from typing import NewType

from collections.abc import Awaitable, Callable

from .messages import Event, Subscription

# Внутренний адрес группы соединений
Room = NewType("Room", str)

type RoomResolver = Callable[[Subscription], Awaitable[Room]]

type RealtimePublisher[T] = Callable[[Event[T], Room], Awaitable[None]]

__all__ = ["RealtimePublisher", "Room", "RoomResolver"]
