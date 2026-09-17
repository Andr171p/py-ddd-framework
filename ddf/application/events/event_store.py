from typing import Protocol

from collections.abc import Sequence

from .types import CollectedEvent


class EventStore(Protocol):

    async def record_all(self, events: Sequence[CollectedEvent]) -> None: ...

    async def find(self, event_type: ...) -> ...: ...
