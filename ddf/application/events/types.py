from collections.abc import Awaitable, Callable, Sequence

from ddf.domain.events import Event

type EventPublisher = Callable[[Sequence[Event]], Awaitable[None]]

__all__ = ["EventPublisher"]
