# Рецепт: репозиторий с кэшем

Ниже — composition root для FastAPI: сессия создаётся на запрос, SQL-репозиторий оборачивается cache-aside декоратором, а use case получает только контракт.

```python
from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ddf.infra.cache.cached_repository import CachedRepository
from ddf.infra.cache.redis.redis_cache import RedisCache
from ddf.infra.cache.redis.serializers import OrJsonSerializer


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def get_users(
    session: AsyncSession = Depends(get_session),
) -> CachedRepository[User]:
    database_repo = UserRepository(session)
    cache = RedisCache(redis_client, OrJsonSerializer(User), ttl=300)
    return CachedRepository(database_repo, cache, prefix="identity:user")
```

## Границы рецепта

Кэшируется только `read(id)`, а не `find()`. Списки часто зависят от фильтров, сортировки и прав доступа; кэширование их одним ключом приводит к ошибкам и сложной инвалидации. Добавляйте кэш списка только после измерений и с ключом, включающим все значимые параметры.

При обновлении два параллельных запроса могут временно увидеть старый объект. Если для операции нужна строгая актуальность (например, проверка лимита), читайте из базы внутри транзакции, а не через кэш.

!!! tip "Измеряйте"

    До внедрения следите за cache hit ratio, latency базы и количеством ключей. Кэш с низким hit ratio обычно лишь добавляет сеть, сериализацию и новую точку отказа.
