from typing import Protocol

from .models import RateLimitPolicy, RateLimitResult


class RateLimiter(Protocol):
    async def acquire(self, key: str, policy: RateLimitPolicy, *, cost: int = -1) -> RateLimitResult: ...
