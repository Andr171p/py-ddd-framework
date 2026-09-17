from uuid import UUID

from ddf.application.cache import Cache
from ddf.application.repositories import Repository, RepositoryDecorator
from ddf.domain.models import Entity


def build_cache_key(prefix: str, uid: UUID) -> str:
    return f"{prefix}:{uid}"


class CachedRepository[EntityT: Entity](RepositoryDecorator[EntityT]):
    """Декоратор для репозитория реализующий Cache-Aside паттерн."""

    def __init__(self, repo: Repository[EntityT], cache: Cache[EntityT], prefix: str) -> None:
        super().__init__(repo)
        self.cache = cache
        self.prefix = prefix

    async def create(self, entity: EntityT) -> EntityT:
        entity = await self._repo.create(entity)

        key = build_cache_key(self.prefix, entity.id)
        await self.cache.set(key, entity)

        return entity

    async def read(self, uid: UUID) -> EntityT | None:
        key = build_cache_key(self.prefix, uid)

        if (entity := await self.cache.get(key)) is not None:
            return entity

        entity = await self._repo.read(uid)

        if entity:
            await self.cache.set(key, entity)

        return entity

    async def update(self, entity: EntityT) -> None:
        """Обновление в БД + инвалидация кеша (обновление кеша при следующем чтении)."""

        await self._repo.update(entity)

        key = build_cache_key(self.prefix, entity.id)
        await self.cache.delete(key)

    async def delete(self, uid: UUID) -> None:
        await self._repo.delete(uid)

        key = build_cache_key(self.prefix, uid)
        await self.cache.delete(key)

    async def exists(self, uid: UUID) -> bool:
        """Не использует кеш, запрос идёт к источнику истины."""

        return await self._repo.exists(uid)
