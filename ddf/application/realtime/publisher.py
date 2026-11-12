from typing import Any, Protocol

from .messages import Event
from .types import Room


class RealtimePublisher(Protocol):
    async def publish(self, event: Event[Any], *, to: Room) -> None: ...
