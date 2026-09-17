from typing import Any

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

_event_correlation_id: ContextVar[UUID | None] = ContextVar("event_correlation_id", default=None)

_event_meta: ContextVar[dict[str, Any] | None] = ContextVar("event_meta", default=None)


def get_event_correlation_id() -> UUID | None:
    """Возвращает correlation ID текущей операции."""
    return _event_correlation_id.get()


def get_event_meta() -> dict[str, Any]:
    """Возвращает копию метаданных текущей операции."""
    return dict(_event_meta.get() or {})


def get_event_context() -> tuple[UUID | None, dict[str, Any]]:
    """Возвращает текущий контекст событий."""
    return get_event_correlation_id(), get_event_meta()


@contextmanager
def use_event_context(
    *,
    correlation_id: UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> Iterator[None]:
    """
    Устанавливает контекст для событий в пределах текущей операции.

    Предыдущее значение автоматически восстанавливается после выхода
    из контекстного менеджера.
    """

    correlation_token = _event_correlation_id.set(correlation_id)
    meta_token = _event_meta.set(dict(meta) if meta else None)

    try:
        yield
    finally:
        _event_correlation_id.reset(correlation_token)
        _event_meta.reset(meta_token)
