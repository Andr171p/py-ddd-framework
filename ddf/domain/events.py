from typing import ClassVar

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class Event:
    """Базовый класс для всех доменных событий."""

    event_id: uuid.UUID = field(default_factory=uuid.uuid7)  # type: ignore
    event_type: ClassVar[str]

    occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = field(default=1)
