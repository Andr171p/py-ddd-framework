import asyncio
import logging

from ddf.application.cache import Cache

logger = logging.getLogger(__name__)


class MultiLevelCache[T]:
    def __init__(self, *caches: Cache[T]) -> None:
        self._caches = caches

    async def get(self, key: str) -> T | None:
        """
        Ищет ключ по цепочке кэшей.
        При нахождении - каскадно заполняет все предыдущие уровни.
        """

        missed_caches: list[Cache[T]] = []

        for cache in self._caches:
            if (value := await cache.get(key)) is not None:
                if missed_caches:
                    await asyncio.gather(*(missed_cache.set(key, value) for missed_cache in missed_caches))

                return value

            missed_caches.append(cache)

        return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Параллельно пишет во все уровни кеша."""
        await asyncio.gather(*(cache.set(key, value, ttl) for cache in self._caches))

    async def delete(self, key: str) -> None:
        """Параллельно удаляет из всех уровней кэша."""
        await asyncio.gather(*(cache.delete(key) for cache in self._caches))

    async def exists(self, key: str) -> bool:
        """Вернет True, если ключ есть хотя бы на одном уровне."""
        results = await asyncio.gather(*(cache.exists(key) for cache in self._caches))
        return any(results)
