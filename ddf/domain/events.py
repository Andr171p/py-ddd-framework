from typing import ClassVar

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Event:
    """Базовый класс для всех доменных событий."""

    _registry: ClassVar[dict[str, type["Event"]]] = {}

    event_id: uuid.UUID = field(default_factory=uuid.uuid7)  # type: ignore
    event_type: ClassVar[str]

    occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = field(default=1)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        if (event_type := getattr(cls, "event_type", None)) is None:
            return

        if event_type in cls._registry:
            registered = cls._registry[event_type]
            raise ValueError(f"Event type {event_type!r} is already registered by {registered.__qualname__}.")

        cls._registry[event_type] = cls

    @classmethod
    def get_event_class(cls, event_type: str) -> type["Event"] | None:
        return cls._registry.get(event_type)
