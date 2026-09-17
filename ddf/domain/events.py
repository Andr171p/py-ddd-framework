from typing import ClassVar

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Event:
    """Базовый класс для всех доменных событий."""

    event_id: UUID = field(default_factory=uuid4)
    event_type: ClassVar[str]

    occurred_on: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = field(default=1)
