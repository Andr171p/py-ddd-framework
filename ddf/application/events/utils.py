from typing import Any

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, fields

from ddf.domain.events import Event

_EVENT_FIELDS: frozenset[str] = frozenset(field.name for field in fields(Event))


def get_event_payload(event: Event) -> dict[str, Any]:
    """Получает кастомные поля события (полезная нагрузка)."""

    event_dict = asdict(event)
    return {k: v for k, v in event_dict.items() if k not in _EVENT_FIELDS}


async def run_in_parallel[T](
    items: Iterable[T],
    worker: Callable[[T], Awaitable[None]],
    max_concurrent: int | None = None,
) -> None:
    """
    Параллельно выполняет worker для каждого элемента из массива.
    Безопасно работает с генераторами, не сжирая память.
    """

    if not max_concurrent:
        await asyncio.gather(*(worker(item) for item in items), return_exceptions=False)
        return

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _worker_wrapper(item: T) -> None:
        async with semaphore:
            await worker(item)

    await asyncio.gather(*(_worker_wrapper(item) for item in items), return_exceptions=False)


async def run_in_sequence[T](items: Iterable[T], worker: Callable[[T], Awaitable[None]]) -> None:
    """Последовательно выполняет worker для каждого элемента (FIFO)."""

    for item in items:
        await worker(item)
