from typing import Any

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass(slots=True, kw_only=True)
class OutboxMessage:

    id: uuid.UUID = field(default_factory=uuid.uuid7)  # type: ignore
    type: str
    occurred_on: datetime
    payload: Mapping[str, Any]
    meta: Mapping[str, Any] = field(default_factory=dict)
    attempts: int = 0

    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
    failed_at: datetime | None = None
    last_error: str | None = None

    @property
    def status(self) -> OutboxStatus:
        if self.processed_at is not None:
            return OutboxStatus.PROCESSED

        if self.failed_at is not None:
            return OutboxStatus.FAILED

        return OutboxStatus.PENDING

    def mark_processed(self) -> None:
        self.processed_at = datetime.now(UTC)
        self.last_error = None

    def mark_failed(self, error: str, *, retry_after: timedelta, max_attempts: int = 5) -> None:
        self.attempts += 1
        self.last_error = error

        if self.attempts >= max_attempts:
            self.failed_at = datetime.now(UTC)
        else:
            self.available_at = datetime.now(UTC) + retry_after
