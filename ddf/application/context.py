from typing import Any

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

_context: ContextVar[dict[str, Any] | None] = ContextVar("app_context", default=None)


def get_context() -> dict[str, Any]:
    return dict(_context.get() or {})


def get_context_value[T](key: str, default: T | None = None) -> Any | T | None:
    return get_context().get(key, default)


@contextmanager
def use_context(values: Mapping[str, Any]) -> Iterator[None]:
    token = _context.set(dict(values))

    try:
        yield
    finally:
        _context.reset(token)


@contextmanager
def extend_context(values: Mapping[str, Any]) -> Iterator[None]:
    context = {**get_context(), **values}
    token = _context.set(context)

    try:
        yield
    finally:
        _context.reset(token)
