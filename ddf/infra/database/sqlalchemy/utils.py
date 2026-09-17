from typing import Any, Literal, cast

import base64
import binascii
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import ColumnElement, Select, and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ddf.application.dtos import (
    CursorPagination,
    OffsetPagination,
    Page,
    Pagination,
    Sort,
    SortDirection,
    create_page,
)

from .base import Base
from .types import SortFunc

type CursorField = Literal["id", "created_at", "updated_at"]

_ALLOWED_CURSOR_FIELDS: frozenset[CursorField] = frozenset({"id", "created_at", "updated_at"})


class _CursorPayload(BaseModel):
    field: str
    direction: SortDirection

    id: UUID
    value: datetime | None = None

# ==========================================================================================================
# Cursor codec
# ==========================================================================================================


def _encode_cursor(payload: _CursorPayload,) -> str:
    """
    Кодирует внутреннее состояние cursor в URL-safe Base64.

    Padding удаляется, чтобы cursor был немного компактнее
    и лучше выглядел внутри query parameter.
    """

    raw = payload.model_dump_json(exclude_none=True).encode("utf-8")

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> _CursorPayload:
    """Декодирует и валидирует opaque cursor."""

    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode((cursor + padding).encode("ascii"), altchars=b"-_", validate=True)
        return _CursorPayload.model_validate_json(raw)

    except (
        binascii.Error,
        UnicodeEncodeError,
        UnicodeDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise ValueError("Invalid pagination cursor.") from exc


# =========================================================================================================
# Sorting
# =========================================================================================================


def _get_sort_func(direction: SortDirection) -> SortFunc:
    return asc if direction.lower() == "asc" else desc


def _get_model_column[ModelT: Base](model: type[ModelT], field: str) -> ...:
    """Возвращает mapped column ORM модели."""

    if model.__table__.c.get(field) is None:
        raise ValueError(f"Field {field!r} not declared in model {model.__tablename__!r}.")

    return getattr(model, field)


def apply_sorting[ModelT: Base](
    stmt: Select[tuple[ModelT]],
    model: type[ModelT],
    sort: Sort | None = None,
) -> Select[tuple[ModelT]]:
    """
    Применяет стабильную сортировку.

    Если сортировка явно не передана, используется UUIDv7 PK:
        ORDER BY id DESC

    Для любого неуникального поля id автоматически добавляется
    как tie-breaker:
        ORDER BY created_at DESC, id DESC
    """

    stmt = stmt.order_by(None)

    if sort is None:
        return stmt.order_by(model.id.desc())

    column = _get_model_column(model, sort.field)
    sort_func = _get_sort_func(sort.direction)

    if sort.field == "id":
        return stmt.order_by(sort_func(model.id))

    return stmt.order_by(sort_func(column), sort_func(model.id))

# ==========================================================================================================
# Cursor ordering
# ==========================================================================================================


def _resolve_cursor_sort(sort: Sort | None) -> tuple[CursorField, SortDirection]:
    """
    Определяет keyset по которому работает cursor пагинация.

    Cursor пагинация намеренно поддерживает ограниченный набор
    стабильных и индексируемых полей.
    """

    if sort is None:
        return "id", "desc"

    if sort.field not in _ALLOWED_CURSOR_FIELDS:
        raise ValueError(
            "Cursor pagination supports sorting only by "
            f"{sorted(_ALLOWED_CURSOR_FIELDS)}; got {sort.field!r}."
        )

    return cast(CursorField, sort.field), sort.direction


def _validate_cursor(payload: _CursorPayload, *, field: CursorField, direction: SortDirection) -> None:
    """
    Проверяет, что cursor создан для текущей сортировки.

    Например cursor от:
        created_at:desc

    нельзя использовать с:
        updated_at:asc
    """

    if payload.field != field:
        raise ValueError("Cursor field does not match current sorting.")

    if payload.direction.lower() != direction.lower():
        raise ValueError("Cursor direction does not match current sorting.")

    if field != "id" and payload.value is None:
        raise ValueError(f"Cursor value is required for field {field!r}.")


def _build_cursor_predicate[ModelT: Base](
    model: type[ModelT],
    *,
    field: CursorField,
    direction: SortDirection,
    payload: _CursorPayload,
) -> ColumnElement[bool]:
    """
    Создаёт keyset WHERE предикат

    id DESC:
        id < :id

    Created_at DESC:
        created_at < :value
        OR (
            created_at = :value
            AND id < :id
        )

    Created_at ASC:
        created_at > :value
        OR (
            created_at = :value
            AND id > :id
        )
    """

    ascending = direction.lower() == "asc"

    if field == "id":
        if ascending:
            return model.id > payload.id

        return model.id < payload.id

    value = payload.value

    if value is None:
        raise ValueError(f"Cursor value is required for {field!r}.")

    column = getattr(model, field)

    if ascending:
        return or_(column > value, and_(column == value, model.id > payload.id))

    return or_(column < value, and_(column == value, model.id < payload.id))


def _build_next_cursor[ModelT: Base](model: ModelT, *, field: CursorField, direction: SortDirection) -> str:
    """Создаёт cursor из последней модели текущей страницы."""

    if field == "id":
        payload = _CursorPayload(field=field, direction=direction, id=model.id)
        return _encode_cursor(payload)

    value = getattr(model, field)

    if not isinstance(value, datetime):
        raise TypeError(f"Cursor field {field!r} must contain datetime, got {type(value)!r}.")

    payload = _CursorPayload(
        field=field,
        direction=direction,
        id=model.id,
        value=value,
    )
    return _encode_cursor(payload)

# ==========================================================================================================
# Pagination strategies
# ==========================================================================================================


async def _paginate_by_cursor[ModelT: Base](
    session: AsyncSession,
    stmt: Select[tuple[ModelT]],
    pagination: CursorPagination,
    model: type[ModelT],
    *,
    sort: Sort | None = None,
) -> tuple[list[ModelT], dict[str, Any]]:
    """
    Keyset pagination.

    Поддерживаемые поля:
        - id
        - created_at
        - updated_at

    UUIDv7 используется как:
        - основной cursor для sort=id;
        - уникальный tie-breaker для created_at/updated_at.

    Для определения has_next запрашивается size + 1 элементов.
    """

    field, direction = _resolve_cursor_sort(sort)

    stmt = apply_sorting(stmt, model, sort)

    if pagination.cursor is not None:
        payload = _decode_cursor(pagination.cursor)

        _validate_cursor(payload, field=field, direction=direction)

        predicate = _build_cursor_predicate(
            model,
            field=field,
            direction=direction,
            payload=payload,
        )
        stmt = stmt.where(predicate)

    result = await session.scalars(stmt.limit(pagination.size + 1))
    models = list(result.all())

    has_next = len(models) > pagination.size

    models = models[:pagination.size]
    next_cursor: str | None = None

    if has_next and models:
        next_cursor = _build_next_cursor(models[-1], field=field, direction=direction)

    return models, {"next_cursor": next_cursor, "has_next": has_next}


async def _paginate_by_offset[ModelT: Base](
    session: AsyncSession,
    stmt: Select[tuple[ModelT]],
    pagination: OffsetPagination,
    model: type[ModelT],
    *,
    sort: Sort | None = None,
) -> tuple[list[ModelT], dict[str, Any]]:
    """Классическая LIMIT/OFFSET пагинация."""

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())

    total = await session.scalar(count_stmt) or 0

    stmt = apply_sorting(stmt, model, sort)
    stmt = stmt.offset(pagination.offset).limit(pagination.size)

    result = await session.scalars(stmt)
    return list(result.all()), {"total": total}

# ==========================================================================================================
# Public API
# ==========================================================================================================


async def paginate[ModelT: Base, ItemT](
    session: AsyncSession,
    model: type[ModelT],
    stmt: Select[tuple[ModelT]],
    pagination: Pagination,
    *,
    from_model: Callable[[ModelT], ItemT] | None = None,
    sort: Sort | None = None,
) -> Page[Any]:
    """Применяет выбранную стратегию пагинации к SQLAlchemy запросу."""

    if isinstance(pagination, CursorPagination):
        models, kwargs = await _paginate_by_cursor(
            session=session,
            stmt=stmt,
            pagination=pagination,
            model=model,
            sort=sort,
        )

    elif isinstance(pagination, OffsetPagination):
        models, kwargs = await _paginate_by_offset(
            session=session,
            stmt=stmt,
            pagination=pagination,
            model=model,
            sort=sort,
        )

    else:
        raise TypeError(f"Unsupported pagination type: {type(pagination)!r}.")

    items = [from_model(model) for model in models] if from_model is not None else models
    return create_page(pagination, items, **kwargs)
