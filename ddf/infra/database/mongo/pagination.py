from __future__ import annotations

from typing import Any

import base64
from collections.abc import Mapping

from bson import json_util
from pymongo.asynchronous.collection import AsyncCollection

from ddf.application.dtos import CursorPagination, OffsetPagination, Page, Pagination, create_page

from .mongo_base_model import MongoBaseModel


def _encode_cursor(document: Mapping[str, Any], *, sort: list[tuple[str, int]]) -> str:
    payload = {
        "v": 1,
        "values": [
            value
            for field, _ in sort
            if (value := document.get(field)) is not None
        ],
    }

    raw = json_util.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> list[Any]:
    padding = "=" * (-len(cursor) % 4)

    try:
        raw = base64.urlsafe_b64decode(cursor + padding)
        payload = json_util.loads(raw)
    except Exception as exc:
        raise ValueError("Invalid pagination cursor.") from exc

    if payload.get("v") != 1:
        raise ValueError("Unsupported pagination cursor version.")

    values = payload.get("values")

    if not isinstance(values, list):
        raise ValueError("Invalid pagination cursor payload.")

    return values


def _build_cursor_filter(*, cursor: str, sort: list[tuple[str, int]]) -> dict[str, Any]:
    values = _decode_cursor(cursor)

    if len(values) != len(sort):
        raise ValueError("Cursor does not match current sort.")

    clauses: list[dict[str, Any]] = []

    for index, ((field, direction), value) in enumerate(zip(sort, values, strict=True)):
        clause: dict[str, Any] = {}

        for previous_index in range(index):
            previous_field, _ = sort[previous_index]
            previous_value = values[previous_index]

            clause[previous_field] = previous_value

        operator = "$gt" if direction == 1 else "$lt"

        clause[field] = {operator: value}
        clauses.append(clause)

    if len(clauses) == 1:
        return clauses[0]

    return {"$or": clauses}


def _merge_filters(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if not left:
        return right

    if not right:
        return left

    return {"$and": [left, right]}


async def _paginate_by_offset[ModelT: MongoBaseModel](
    collection: AsyncCollection,
    *,
    model: type[ModelT],
    filter_: dict[str, Any],
    sort: list[tuple[str, int]],
    pagination: OffsetPagination,
) -> Page[ModelT]:
    total = await collection.count_documents(filter_)
    cursor = (
        collection
        .find(filter_)
        .sort(sort)
        .skip(pagination.offset)
        .limit(pagination.size)
    )

    items = [model.model_validate(doc) async for doc in cursor]
    return create_page(pagination, items, total=total)


async def _paginate_by_cursor[ModelT: MongoBaseModel](
    collection: AsyncCollection,
    *,
    model: type[ModelT],
    filter_: dict[str, Any],
    sort: list[tuple[str, int]],
    pagination: CursorPagination,
) -> Page[ModelT]:
    effective_filter = filter_

    if pagination.cursor is not None:
        cursor_filter = _build_cursor_filter(cursor=pagination.cursor, sort=sort)
        effective_filter = _merge_filters(filter_, cursor_filter)

    cursor = (
        collection
        .find(effective_filter)
        .sort(sort)
        .limit(pagination.size + 1)
    )

    docs = [doc async for doc in cursor]

    has_next = len(docs) > pagination.size
    docs = docs[:pagination.size]
    next_cursor: str | None = None

    if has_next and docs:
        next_cursor = _encode_cursor(docs[-1], sort=sort)

    items = [model.model_validate(doc) for doc in docs]
    return create_page(pagination, items, next_cursor=next_cursor, has_next=has_next)


async def paginate[ModelT: MongoBaseModel](
    collection: AsyncCollection,
    *,
    model: type[ModelT],
    filter_: dict[str, Any],
    sort: list[tuple[str, int]],
    pagination: Pagination,
) -> Page[ModelT]:
    """Применяет выбранную стратегию пагинации к Mongo запросу."""

    match pagination:
        case OffsetPagination():
            return await _paginate_by_offset(
                collection,
                model=model,
                filter_=filter_,
                sort=sort,
                pagination=pagination,
            )

        case CursorPagination():
            return await _paginate_by_cursor(
                collection,
                model=model,
                filter_=filter_,
                sort=sort,
                pagination=pagination,
            )

    raise TypeError(f"Unsupported pagination: {type(pagination).__name__}.")
