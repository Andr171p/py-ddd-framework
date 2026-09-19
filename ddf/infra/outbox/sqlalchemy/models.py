from typing import Any

from sqlalchemy import Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ddf.infra.database.sqlalchemy import Base
from ddf.infra.database.sqlalchemy.types import DatatimeTz, DatetimeTzNull, Str255, StrNull, UuidPk


class OutboxMessageOrm(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[UuidPk]
    type_: Mapped[Str255]
    occurred_on: Mapped[DatatimeTz]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    meta: dict[str, Any] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int]

    available_at: Mapped[DatatimeTz]
    processed_at: Mapped[DatetimeTzNull]
    failed_at: Mapped[DatetimeTzNull]
    last_error: Mapped[StrNull]

    __table_args__ = (
        Index(
            "ix_outbox_messages_pending",
            "available_at",
            "id",
            postgresql_where=text("processed_at IS NULL AND failed_at IS NULL"),
        ),
    )
