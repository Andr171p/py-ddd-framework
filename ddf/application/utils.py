from typing import Any

from collections.abc import AsyncIterable, Awaitable, Callable
from uuid import UUID

from ddf.domain.models import Entity

from .dtos import CursorPagination, Pagination, next_pagination
from .exceptions import NotFoundError
from .repositories import Repository


async def get_or_raise_not_found[EntityT: Entity](
    func: Callable[[UUID], Awaitable[EntityT | None]],
    uid: UUID,
    entity_type: type[EntityT],
) -> EntityT:
    if (obj := await func(uid)) is None:
        raise NotFoundError(f"{entity_type.__class__.__name__} with ID {uid} not found.")

    return obj


async def iterate_batches[EntityT: Entity](
    repository: Repository[EntityT],
    initial_pagination: Pagination | None = None,
    default_size: int = 50,
    **kwargs: Any,
) -> AsyncIterable[tuple[EntityT, ...]]:
    """
    Асинхронно считывает всю коллекцию доменных сущностей из репозитория потоковыми батчами.

    Функция инкапсулирует полиморфный обход данных и автоматически адаптируется
    как под курсорную (Cursor), так и под классическую (Offset) пагинацию на основе
    возвращаемых метаданных. Обеспечивает безопасное и эффективное сканирование
    больших объемов данных (курсорный режим гарантирует скорость выполнения O(1)
    на каждом шаге цикла).

    Итерация прерывается автоматически, если база данных вернула пустую страницу
    или метаданные текущей страницы указывают на отсутствие следующих элементов.
    """

    pagination = initial_pagination or CursorPagination(cursor=None, size=default_size)

    while True:
        page = await repository.find(pagination, **kwargs)

        if not page.items:
            break

        yield tuple(page.items)

        if not page.meta.has_next:
            break

        pagination = next_pagination(pagination, page.meta)


__all__ = ["get_or_raise_not_found", "iterate_batches"]
