from typing import Protocol

from .policies import ConcurrencyPolicy


class ConcurrencyLease(Protocol):
    """Отвечает за продление и освобождение занятого слота."""

    async def renew(self) -> bool: ...

    async def release(self) -> None: ...


class ConcurrencyLimiter(Protocol):
    """Отвечает за выделение свободного слота."""

    async def acquire(self, key: str, policy: ConcurrencyPolicy) -> ConcurrencyLease | None: ...


__all__ = ["ConcurrencyLease", "ConcurrencyLimiter"]
