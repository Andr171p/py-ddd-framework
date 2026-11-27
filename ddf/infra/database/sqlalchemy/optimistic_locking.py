from typing import Any, Protocol, runtime_checkable

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Column, inspect, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import ColumnProperty

from ddf.application.exceptions import ConcurrentModificationError
from ddf.domain.models import Entity

from .base import Base
from .data_mapper import DataMapper

_EXCLUDED_FIELDS = frozenset({"id", "version", "created_at", "updated_at"})


@runtime_checkable
class _Versioned(Protocol):
    id: UUID
    version: int
    updated_at: datetime


def _is_updatable_column_attr(attr: ColumnProperty[Any], *, excluded_fields: frozenset[str]) -> bool:
    if attr.key in excluded_fields or len(attr.columns) != 1:
        return False

    column = attr.columns[0]
    if not isinstance(column, Column):
        return False

    return not column.primary_key and column.computed is None and column.identity is None


async def update_versioned[EntityT: Entity, ModelT: Base](
    session: AsyncSession,
    entity: EntityT,
    *,
    data_mapper: DataMapper[EntityT, ModelT],
    model_cls: type[ModelT],
    exclude: frozenset[str] | None = None,
) -> None:
    """Обновляет сущность с проверкой ожидаемой версии.

    При конкурентном изменении выбрасывает ```ConcurrentModificationError``.

    Не выполняет commit транзакции.
    """

    if not isinstance(entity, _Versioned):
        raise TypeError(f"{type(entity).__name__} does not support versioned updates.")

    expected_version = entity.version
    now = datetime.now(UTC)

    model = data_mapper.to_model(entity)
    mapper = inspect(model_cls)
    excluded_fields = _EXCLUDED_FIELDS if exclude is None else _EXCLUDED_FIELDS | exclude

    values = {
        attr.key: getattr(model, attr.key)
        for attr in mapper.column_attrs
        if _is_updatable_column_attr(attr, excluded_fields=excluded_fields)
    }
    values.update(version=expected_version + 1, updated_at=now)

    stmt = (
        update(model_cls)
        .where(model_cls.id == entity.id, model_cls.version == expected_version)
        .values(values)
        .returning(model_cls.version)
    )
    result = await session.execute(stmt)

    if (version := result.scalar_one_or_none()) is None:
        raise ConcurrentModificationError(
            f"{type(entity).__name__} {entity.id!r} "
            f"has been concurrently modified "
            f"(expected version: {expected_version}).",
        )

    entity.version = version
    entity.updated_at = now


__all__ = ["update_versioned"]
