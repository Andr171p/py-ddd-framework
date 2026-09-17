import asyncio
import contextlib
import time


class InMemoryCache[T]:
    def __init__(self, ttl: float | None = None, cleanup_interval: float = 60) -> None:
        self.storage: dict[str, tuple[T, float | None]] = {}
        self.ttl = ttl
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task[None] | None = None

    async def get(self, key: str) -> T | None:
        """Получение с ленивым удалением по TTL."""

        if key not in self.storage:
            return None

        value, expires = self.storage[key]
        if expires is not None and time.monotonic() >= expires:
            del self.storage[key]
            return None

        return value

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        expires = None

        effective_ttl = ttl if ttl is not None else self.ttl
        if effective_ttl is not None:
            expires = time.monotonic() + effective_ttl

        self.storage[key] = (value, expires)

    async def delete(self, key) -> None:
        if key not in self.storage:
            return

        del self.storage[key]

    async def exists(self, key: str) -> bool:
        return key in self.storage

    async def _cleanup_loop(self) -> None:
        """Бесконечный цикл для отчистки протухшего кеша по TTL."""

        while True:
            await asyncio.sleep(self.cleanup_interval)

            now = time.monotonic()

            expired = [
                key
                for key, (value, expires) in self.storage.items()
                if expires is not None and expires <= now
            ]

            for key in expired:
                if key in self.storage:
                    del self.storage[key]

    def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def close(self) -> None:
        if self._cleanup_task is None:
            return

        self._cleanup_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await self._cleanup_task
