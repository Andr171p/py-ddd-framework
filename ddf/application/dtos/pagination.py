from typing import Annotated, Any, Literal, overload

from collections.abc import Callable, Sequence

from fastapi import Depends, Query
from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

_DEFAULT_PAGE_SIZE = 10
_MAX_PAGE_SIZE = 100

type PaginationType = Literal["cursor", "offset"]


class OffsetPagination(BaseModel):
    """Классическая пагинация по номерам страниц."""

    type: Literal["offset"] = Field(default="offset")
    page: PositiveInt = Field(default=1, description="Номер страницы")
    size: PositiveInt = Field(default=_DEFAULT_PAGE_SIZE, le=_MAX_PAGE_SIZE, description="Размер страницы")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class CursorPagination(BaseModel):
    """Курсорная пагинация (keyset)."""

    type: Literal["cursor"] = Field(default="cursor", alias="pagination")
    cursor: str | None = Field(default=None, description="Непрозрачный указатель (Base64) на элемент")
    size: PositiveInt = Field(default=_DEFAULT_PAGE_SIZE, le=_MAX_PAGE_SIZE, description="Размер страницы")


class OffsetMeta(BaseModel):
    """Метаданные классической пагинации для навигации."""

    type: Literal["offset"] = "offset"

    page: PositiveInt = Field(description="Текущая страница")
    size: PositiveInt = Field(description="Размер текущей страницы")
    total: NonNegativeInt = Field(description="Общее количество элементов удовлетворяющих запросу")
    pages: NonNegativeInt = Field(description="Количество страниц")
    has_next: bool = Field(description="Есть ли следующая страница")
    has_prev: bool = Field(description="Есть ли предыдущая страница")


class CursorMeta(BaseModel):
    """Метаданные курсорной пагинации для упрощения навигации."""

    type: Literal["cursor"] = "cursor"

    next_cursor: str | None = Field(default=None, description="")
    has_next: bool = Field(description="Можно ли запросить ещё данных")
    size: PositiveInt = Field(description="Размер батча")


Pagination = Annotated[OffsetPagination | CursorPagination, Field(discriminator="type")]
PaginationMeta = Annotated[OffsetMeta | CursorMeta, Field(discriminator="type")]


class Page[T: Any](BaseModel):
    """Универсальный контейнер для страниц любого типа."""

    items: list[T] = Field(default_factory=list, description="Запрашиваемые элементы")
    meta: PaginationMeta = Field(description="Метаданные пагинации")

    def map[R: Any](self, convert: Callable[[T], R]) -> "Page[R]":
        """Преобразует все элементы страницы к заданому формату."""

        return Page(items=list(map(convert, self.items)), meta=self.meta)


@overload
def create_page[T: Any](pagination: OffsetPagination, items: Sequence[T], total: int) -> Page[T]: ...


@overload
def create_page[T: Any](
    pagination: CursorPagination,
    items: Sequence[T],
    next_cursor: str | None,
    has_next: bool,
) -> Page[T]: ...


def create_page[T: Any](pagination: Pagination, items: Sequence[T], *args: Any, **kwargs: Any) -> Page[T]:
    """Фабрика для создания DTO страниц на основе типа запрошенной пагинации"""

    if isinstance(pagination, OffsetPagination):
        total: int = args[0] if args else kwargs["total"]
        pages = (total + pagination.size - 1) // pagination.size

        return Page(
            items=list(items),
            meta=OffsetMeta(
                page=pagination.page,
                size=pagination.size,
                total=total,
                pages=pages,
                has_next=pagination.page < pages,
                has_prev=pagination.page > 1,
            ),
        )

    if isinstance(pagination, CursorPagination):
        next_cursor: str | None = args[0] if args else kwargs.get("next_cursor")
        has_next: bool = args[1] if len(args) > 1 else kwargs["has_next"]

        return Page(
            items=list(items),
            meta=CursorMeta(
                next_cursor=next_cursor,
                has_next=has_next,
                size=pagination.size,
            )
        )

    raise ValueError(f"Unsupported pagination type: {type(pagination)}.")


@overload
def next_pagination(pagination: OffsetPagination, meta: OffsetMeta) -> OffsetPagination: ...


@overload
def next_pagination(pagination: CursorPagination, meta: CursorMeta) -> CursorPagination: ...


def next_pagination(pagination: Pagination, meta: PaginationMeta) -> Pagination:
    """
    Вычисления следующего шага пагинации.
    Принимает DTO пагинации и метаданные, возвращает обновленный DTO того же типа.
    """

    if isinstance(pagination, OffsetPagination) and isinstance(meta, OffsetMeta):
        return OffsetPagination(page=pagination.page + 1, size=pagination.size)

    if isinstance(pagination, CursorPagination) and isinstance(meta, CursorMeta):
        return CursorPagination(cursor=meta.next_cursor, size=pagination.size)

    raise ValueError(f"Missmatch between pagination ({type(pagination)}) and meta ({type(meta)}).")


def get_pagination(
    pagination_type: Annotated[PaginationType, Query(alias="pagination")] = "offset",
    size: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 50,
    page: Annotated[int | None, Query(ge=1)] = 1,
    cursor: Annotated[str | None, Query()] = None,
) -> Pagination:
    match pagination_type:
        case "offset":
            return OffsetPagination(page=page, size=size)
        case "cursor":
            return CursorPagination(cursor=cursor, size=size)

    raise ValueError(f"Unsupported pagination type: {pagination_type}.")


PaginationQuery = Annotated[Pagination, Depends(get_pagination)]
