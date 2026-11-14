import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, DateTime, Table, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from ddf.infra.database.sqlalchemy.base import Base
from ddf.infra.database.sqlalchemy.repository import SqlAlchemyRepository

from .dataset import Ticket, TicketSeed, entity_from_seed, load_tickets

FILTER_FIELDS = (
    "id",
    "title",
    "status",
    "priority",
    "assigneeName",
    "urgent",
    "dueAt",
)


class TicketRow(Base):
    __tablename__ = "dsl_tickets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    code: Mapped[str]
    organization_id: Mapped[str]
    title: Mapped[str]
    status: Mapped[str]
    priority: Mapped[int]
    assignee_name: Mapped[str | None] = mapped_column(nullable=True)
    urgent: Mapped[bool]
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    internal_note: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketMapper:
    def to_model(self, entity: Ticket) -> TicketRow:
        return TicketRow(
            id=entity.id,
            code=entity.code,
            organization_id=entity.organization_id,
            title=entity.title,
            status=entity.status,
            priority=entity.priority,
            assignee_name=entity.assignee_name,
            urgent=entity.urgent,
            due_at=entity.due_at,
            internal_note=entity.internal_note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    def from_model(self, model: TicketRow) -> Ticket:
        return Ticket(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            code=model.code,
            organization_id=model.organization_id,
            title=model.title,
            status=model.status,
            priority=model.priority,
            assignee_name=model.assignee_name,
            urgent=model.urgent,
            due_at=model.due_at,
            internal_note=model.internal_note,
        )


def search_title(query: str) -> ColumnElement[bool]:
    return TicketRow.title.ilike(f"%{query}%")


class TicketRepository(SqlAlchemyRepository[Ticket, TicketRow]):
    model = TicketRow
    data_mapper = TicketMapper()
    filter_whitelist = FILTER_FIELDS
    search = staticmethod(search_title)


def row_from_seed(seed: TicketSeed) -> TicketRow:
    return TicketMapper().to_model(entity_from_seed(seed))


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(_create_tables)


async def replace_rows(session: AsyncSession) -> None:
    await session.execute(delete(TicketRow))
    session.add_all(row_from_seed(seed) for seed in load_tickets())
    await session.commit()


def _create_tables(connection: Connection) -> None:
    table = TicketRow.__table__
    if not isinstance(table, Table):
        raise TypeError("TicketRow is not mapped to a table.")
    Base.metadata.create_all(connection, tables=[table])
