from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .concurrency_limiter import RedisConcurrencyLimiter

import asyncio


class RedisConcurrencyLease:
    def __init__(self, limiter: "RedisConcurrencyLimiter", key: str, lease_id: str, ttl_ms: int) -> None:
        self._limiter = limiter
        self._key = key
        self._lease_id = lease_id
        self._ttl_ms = ttl_ms

        self._released = False
        self._lock = asyncio.Lock()

    async def renew(self) -> bool:
        async with self._lock:
            if self._released:
                return False

            renewed = await self._limiter.renew_script(keys=[self._key], args=[self._lease_id, self._ttl_ms])
            if not renewed:
                self._released = True

        return bool(renewed)

    async def release(self) -> None:
        async with self._lock:
            if self._released:
                return

            await self._limiter.release_script(keys=[self._key], args=[self._lease_id])
            self._released = True
