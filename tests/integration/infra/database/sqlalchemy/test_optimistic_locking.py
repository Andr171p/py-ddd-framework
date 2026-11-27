"""Integration-тесты update_versioned на PostgreSQL."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ddf.application.exceptions import ConcurrentModificationError
from ddf.application.outbox.utils import save_events_to_outbox
from ddf.domain.models import Entity
from ddf.infra.database.sqlalchemy.optimistic_locking import update_versioned
from ddf.infra.outbox.sqlalchemy.models import OutboxMessageOrm
from ddf.infra.outbox.sqlalchemy.outbox_store import SqlAlchemyOutboxStore
from tests.helpers.sqlalchemy.versioned_catalog import (
    WIDGET_MAPPER,
    Widget,
    WidgetRenamed,
    WidgetRow,
    make_widget,
)

pytestmark = pytest.mark.usefixtures("clean_tables")


async def _insert(session: AsyncSession, widget: Widget) -> WidgetRow:
    row = WIDGET_MAPPER.to_model(widget)
    session.add(row)
    await session.commit()
    return row


async def _load_row(session: AsyncSession, widget_id) -> WidgetRow:
    row = await session.get(WidgetRow, widget_id)
    assert row is not None
    return row


async def test_update_versioned(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="alpha", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="beta",
            code=widget.code,
            version=0,
        )
        entity.created_at = widget.created_at
        entity.updated_at = widget.updated_at

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )
        await session.commit()

        assert entity.version == 1
        assert entity.name == "beta"

        row = await _load_row(session, widget.id)
        assert row.name == "beta"
        assert row.version == 1
        assert row.updated_at == entity.updated_at


async def test_stale_version_rejected(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="v0", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as first:
        current = make_widget(widget_id=widget.id, name="v1", code=widget.code, version=0)
        current.created_at = widget.created_at
        await update_versioned(first, current, data_mapper=WIDGET_MAPPER, model_cls=WidgetRow)
        await first.commit()

    async with session_factory() as stale:
        outdated = make_widget(widget_id=widget.id, name="stale", code=widget.code, version=0)
        outdated.created_at = widget.created_at

        with pytest.raises(ConcurrentModificationError, match="expected version: 0"):
            await update_versioned(
                stale,
                outdated,
                data_mapper=WIDGET_MAPPER,
                model_cls=WidgetRow,
            )
            await stale.commit()

    async with session_factory() as session:
        row = await _load_row(session, widget.id)
        assert row.version == 1
        assert row.name == "v1"


async def test_concurrent_updates(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="base", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async def attempt(name: str) -> str:
        async with session_factory() as session:
            entity = make_widget(
                widget_id=widget.id,
                name=name,
                code=widget.code,
                version=0,
            )
            entity.created_at = widget.created_at
            try:
                await update_versioned(
                    session,
                    entity,
                    data_mapper=WIDGET_MAPPER,
                    model_cls=WidgetRow,
                )
                await session.commit()
            except ConcurrentModificationError:
                await session.rollback()
                return "conflict"
            return "ok"

    outcomes = await asyncio.gather(attempt("writer-a"), attempt("writer-b"))
    assert outcomes.count("ok") == 1
    assert outcomes.count("conflict") == 1

    async with session_factory() as session:
        row = await _load_row(session, widget.id)
        assert row.version == 1
        assert row.name in {"writer-a", "writer-b"}


async def test_updated_at_consistency(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="ts", version=0)
    old_updated_at = widget.updated_at - timedelta(hours=1)
    widget.updated_at = old_updated_at
    widget.created_at = old_updated_at

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="ts-updated",
            code=widget.code,
            version=0,
        )
        entity.created_at = widget.created_at
        entity.updated_at = old_updated_at

        before = datetime.now(UTC)
        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )
        after = datetime.now(UTC)
        await session.commit()

        assert before <= entity.updated_at <= after
        assert entity.updated_at != old_updated_at

        row = await _load_row(session, widget.id)
        assert row.updated_at == entity.updated_at
        assert row.updated_at.tzinfo is not None


async def test_transaction_rollback(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="rollback-me", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="should-not-persist",
            code=widget.code,
            version=0,
        )
        entity.created_at = widget.created_at

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )
        await session.rollback()

        assert entity.version == 1

    async with session_factory() as session:
        row = await _load_row(session, widget.id)
        assert row.version == 0
        assert row.name == "rollback-me"


async def test_identity_map_synchronized(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="mapped", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        loaded = await _load_row(session, widget.id)
        assert loaded.name == "mapped"
        assert loaded.version == 0

        entity = WIDGET_MAPPER.from_model(loaded)
        entity.name = "identity-synced"

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )

        assert loaded.name == "identity-synced"
        assert loaded.version == entity.version == 1
        assert loaded.updated_at == entity.updated_at

        await session.commit()


async def test_immutable_fields_preserved(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="mutable", code="KEEP-ME", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="changed",
            code="SHOULD-NOT-WRITE",
            version=0,
        )
        entity.created_at = widget.created_at + timedelta(days=1)
        entity.updated_at = widget.updated_at

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
            exclude=frozenset({"code"}),
        )
        await session.commit()

        row = await _load_row(session, widget.id)
        assert row.name == "changed"
        assert row.code == "KEEP-ME"
        assert row.created_at == widget.created_at
        assert row.version == 1


async def test_missing_entity(session_factory: async_sessionmaker[AsyncSession]) -> None:
    entity = make_widget(name="absent", version=0)

    async with session_factory() as session:
        with pytest.raises(ConcurrentModificationError) as exc_info:
            await update_versioned(
                session,
                entity,
                data_mapper=WIDGET_MAPPER,
                model_cls=WidgetRow,
            )

        assert exc_info.value.error_code == "concurrent_modification"


async def test_non_versioned_entity(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        with pytest.raises(TypeError, match="does not support versioned updates"):
            await update_versioned(
                session,
                Entity(),  # type: ignore[arg-type]
                data_mapper=WIDGET_MAPPER,  # type: ignore[arg-type]
                model_cls=WidgetRow,
            )


async def test_versioned_update_with_outbox(session_factory: async_sessionmaker[AsyncSession]) -> None:
    widget = make_widget(name="outbox-base", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="outbox-updated",
            code=widget.code,
            version=0,
        )
        entity.created_at = widget.created_at
        entity.register_event(
            WidgetRenamed(widget_id=widget.id, name="outbox-updated"),
        )

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )
        await save_events_to_outbox(SqlAlchemyOutboxStore(session), entity)
        await session.commit()

        row = await _load_row(session, widget.id)
        assert row.version == 1
        assert row.name == "outbox-updated"

        messages = (await session.execute(select(OutboxMessageOrm))).scalars().all()
        assert len(messages) == 1
        assert messages[0].type_ == "test.widget.renamed"
        assert messages[0].payload["name"] == "outbox-updated"


async def test_versioned_update_with_outbox_rolls_back_together(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    widget = make_widget(name="atomic-base", version=0)

    async with session_factory() as session:
        await _insert(session, widget)

    async with session_factory() as session:
        entity = make_widget(
            widget_id=widget.id,
            name="atomic-updated",
            code=widget.code,
            version=0,
        )
        entity.created_at = widget.created_at
        entity.register_event(
            WidgetRenamed(widget_id=widget.id, name="atomic-updated"),
        )

        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )
        await save_events_to_outbox(SqlAlchemyOutboxStore(session), entity)
        await session.rollback()

    async with session_factory() as session:
        row = await _load_row(session, widget.id)
        assert row.version == 0
        assert row.name == "atomic-base"
        messages = (await session.execute(select(OutboxMessageOrm))).scalars().all()
        assert messages == []
