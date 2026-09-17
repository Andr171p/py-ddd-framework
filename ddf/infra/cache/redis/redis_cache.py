from redis.asyncio import Redis

from .serializers import Serializer


class RedisCache[T]:
    def __init__(
            self,
            redis: Redis,
            serializer: Serializer[T],
            ttl: int | None = None
    ) -> None:
        self.redis = redis
        self.serializer = serializer
        self.ttl = ttl

    async def get(self, key: str) -> T | None:
        if (raw := await self.redis.get(key)) is None:
            return None

        return self.serializer.loads(raw)

    async def set(self, key: str, value: T, ttl: int | None = None) -> None:
        raw = self.serializer.dumps(value)

        effective_ttl = ttl if ttl is not None else self.ttl

        await self.redis.set(key, raw, ex=effective_ttl)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        result = await self.redis.exists(key)
        return result > 0
