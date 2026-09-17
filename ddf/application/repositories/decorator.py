from collections.abc import Sequence
from uuid import UUID

from ddf.application.dtos import Page, Pagination, QueryDTO, Sort
from ddf.domain.models import Entity

from .protocol import Repository


class RepositoryDecorator[EntityT: Entity](Repository[EntityT]):
    def __init__(self, repo: Repository[EntityT]) -> None:
        self._repo = repo

    async def create(self, entity: EntityT) -> EntityT:
        return await self._repo.create(entity)

    async def read(self, uid: UUID) -> EntityT | None:
        return await self._repo.read(uid)

    async def find(
        self,
        pagination: Pagination,
        query: QueryDTO | None = None,
        sort: Sort | None = None,
    ) -> Page[EntityT]:
        return await self._repo.find(pagination=pagination, query=query, sort=sort)

    async def update(self, entity: EntityT) -> None:
        await self._repo.update(entity)

    async def delete(self, uid: UUID) -> None:
        await self._repo.delete(uid)

    async def exists(self, uid: UUID) -> bool:
        return await self._repo.exists(uid)

    async def get_by_ids(self, ids: Sequence[UUID]) -> tuple[EntityT, ...]:
        return await self._repo.get_by_ids(ids)
