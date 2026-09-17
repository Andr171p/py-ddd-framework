from collections.abc import Awaitable, Callable, Sequence

from ddf.domain.events import Event
from ddf.domain.models import Entity

type EventPublisher = Callable[[Sequence[Event]], Awaitable[None]]

type CollectedEvent = tuple[Event, Entity]

__all__ = ["CollectedEvent", "EventPublisher"]
