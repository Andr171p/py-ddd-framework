"""Unit-тесты update_versioned без реальной БД."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from ddf.application.exceptions import ConcurrentModificationError
from ddf.domain.models import Entity
from ddf.infra.database.sqlalchemy.optimistic_locking import update_versioned
from tests.helpers.sqlalchemy.versioned_catalog import WIDGET_MAPPER, WidgetRow, make_widget


@pytest.mark.anyio
async def test_non_versioned_entity() -> None:
    session = AsyncMock()
    entity = Entity()

    with pytest.raises(TypeError, match="does not support versioned updates"):
        await update_versioned(
            session,
            entity,  # type: ignore[arg-type]
            data_mapper=WIDGET_MAPPER,  # type: ignore[arg-type]
            model_cls=WidgetRow,
        )

    session.execute.assert_not_called()


@pytest.mark.anyio
async def test_missing_entity() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    entity = make_widget(name="ghost")

    with pytest.raises(ConcurrentModificationError, match="concurrently modified") as exc_info:
        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )

    assert exc_info.value.error_code == "concurrent_modification"
    session.execute.assert_awaited_once()


@pytest.mark.anyio
async def test_stale_version_rejected() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    entity = make_widget(name="stale", version=3)

    with pytest.raises(ConcurrentModificationError, match="expected version: 3"):
        await update_versioned(
            session,
            entity,
            data_mapper=WIDGET_MAPPER,
            model_cls=WidgetRow,
        )


@pytest.mark.anyio
async def test_update_versioned_mutates_entity_on_success() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 4
    session.execute.return_value = result

    entity = make_widget(name="before", version=3)
    previous_updated_at = entity.updated_at

    await update_versioned(
        session,
        entity,
        data_mapper=WIDGET_MAPPER,
        model_cls=WidgetRow,
    )

    expected_version = 4
    assert entity.version == expected_version
    assert entity.updated_at > previous_updated_at
    session.commit.assert_not_called()
