from typing import Any

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ddf.infra.database.sqlalchemy import Base
from ddf.infra.database.sqlalchemy.types import DatatimeTz, StrNull, UuidNull, UuidPk


class EventOrm(Base):
    __tablename__ = "stored_events"

    event_id: Mapped[UuidPk]
    event_type: Mapped[str]
    version: Mapped[int]
    occurred_on: Mapped[DatatimeTz]
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    entity_id: Mapped[UuidNull]
    entity_type: Mapped[StrNull]

    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    correlation_id: Mapped[UuidNull]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
