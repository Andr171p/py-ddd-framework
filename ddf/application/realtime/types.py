from typing import NewType

from collections.abc import Awaitable, Callable

from .messages import Subscription

Room = NewType("Room", str)

type RoomResolver = Callable[[Subscription], Awaitable[Room]]

__all__ = ["Room", "RoomResolver"]
