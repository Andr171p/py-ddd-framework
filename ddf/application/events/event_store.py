from typing import Protocol

from collections.abc import Sequence

from ddf.domain.events import Event


class EventStore(Protocol):

    async def record_all(self, events: Sequence[Event]) -> None: ...

    async def find(self, event_type: ...) -> ...: ...
