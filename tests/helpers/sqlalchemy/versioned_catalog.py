"""Минимальный versioned-агрегат для тестов optimistic locking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

from ddf.domain.events import Event
from ddf.domain.models import Entity
from ddf.infra.database.sqlalchemy.base import Base
from ddf.infra.outbox.sqlalchemy.models import OutboxMessageOrm


@dataclass(frozen=True, kw_only=True)
class WidgetRenamed(Event):
    event_type = "test.widget.renamed"
    widget_id: uuid.UUID
    name: str


@dataclass(kw_only=True)
class Widget(Entity):
    version: int = 0
    name: str
    code: str = "W-1"


class WidgetRow(Base):
    __tablename__ = "ol_widgets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="W-1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WidgetMapper:
    def to_model(self, entity: Widget) -> WidgetRow:
        return WidgetRow(
            id=entity.id,
            version=entity.version,
            name=entity.name,
            code=entity.code,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    def from_model(self, model: WidgetRow) -> Widget:
        return Widget(
            id=model.id,
            version=model.version,
            name=model.name,
            code=model.code,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )


WIDGET_MAPPER = WidgetMapper()


def make_widget(
    *,
    name: str = "initial",
    code: str = "W-1",
    version: int = 0,
    widget_id: uuid.UUID | None = None,
) -> Widget:
    now = datetime.now(UTC)
    return Widget(
        id=widget_id or uuid.uuid7(),
        version=version,
        name=name,
        code=code,
        created_at=now,
        updated_at=now,
    )


async def create_schema(engine: AsyncEngine, *, with_outbox: bool = False) -> None:
    tables = [WidgetRow.__table__]
    if with_outbox:
        tables.append(OutboxMessageOrm.__table__)

    for table in tables:
        if not isinstance(table, Table):
            raise TypeError(f"{table} is not mapped to a table.")

    async with engine.begin() as connection:
        await connection.run_sync(lambda sync_conn: _create_tables(sync_conn, tables))


def _create_tables(connection: Connection, tables: list[Table]) -> None:
    Base.metadata.create_all(connection, tables=tables)
