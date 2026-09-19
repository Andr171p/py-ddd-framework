from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ddf.application.outbox import OutboxMessage

from . import data_mapper
from .models import OutboxMessageOrm


class SqlAlchemyOutboxStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_all(self, messages: Sequence[OutboxMessage]) -> None:
        if not messages:
            return

        stmt = insert(OutboxMessageOrm).values([data_mapper.to_values(message) for message in messages])
        stmt = stmt.on_conflict_do_update(
            index_element=[OutboxMessageOrm.id],
            set_={
                "attempts": stmt.excluded.attempts,
                "available_at": stmt.excluded.available_at,
                "processed_at": stmt.excluded.processed_at,
                "failed_at": stmt.excluded.failed_at,
                "last_error": stmt.excluded.last_error,
            },
        )

        await self._session.execute(stmt)

    async def acquire(self, *, limit: int) -> tuple[OutboxMessage, ...]:
        if limit <= 0:
            raise ValueError("Outbox acquire limit must be greater than zero.")

        stmt = (
            select(OutboxMessageOrm)
            .where(
                OutboxMessageOrm.processed_at.is_(None),
                OutboxMessageOrm.failed_at.is_(None),
                OutboxMessageOrm.available_at <= func.now(),
            )
            .order_by(
                OutboxMessageOrm.available_at.asc(),
                OutboxMessageOrm.id.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self._session.execute(stmt)
        return tuple(data_mapper.from_model(model) for model in result.scalars().all())
