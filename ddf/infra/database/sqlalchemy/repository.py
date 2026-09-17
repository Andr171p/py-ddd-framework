from typing import ClassVar

from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ddf.application.dtos import Page, Pagination, QueryDTO, Sort
from ddf.domain.models import Entity

from .base import Base
from .data_mapper import DataMapper
from .filters import compile_filter
from .types import SearchFunc
from .utils import paginate


class SqlAlchemyRepository[EntityT: Entity, ModelT: Base]:
    model: type[ModelT]
    data_mapper: DataMapper[EntityT, ModelT]
    search: SearchFunc | None = None
    filter_whitelist: ClassVar[tuple[str, ...]] = ()

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entity: EntityT) -> EntityT:

        model = self.data_mapper.to_model(entity)
        self._session.add(model)
        await self._session.flush()
        return self.data_mapper.from_model(model)

    async def read(self, uid: UUID) -> EntityT | None:
        stmt = select(self.model).where(self.model.id == uid)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return None if model is None else self.data_mapper.from_model(model)

    async def find(
            self,
            pagination: Pagination,
            query: QueryDTO | None = None,
            sort: Sort | None = None,
    ) -> Page[EntityT]:
        stmt = select(self.model)

        if query:
            stmt = stmt.where(
                compile_filter(self.model, query, self.filter_whitelist, self.search),
            )

        return await paginate(
            session=self._session,
            model=self.model,
            stmt=stmt,
            pagination=pagination,
            from_model=self.data_mapper.from_model,
            sort=sort,
        )

    async def update(self, entity: EntityT) -> None:
        model = self.data_mapper.to_model(entity)
        await self._session.merge(model)

    async def delete(self, uid: UUID) -> None:
        stmt = delete(self.model).where(self.model.id == uid)
        await self._session.execute(stmt)

    async def exists(self, uid: UUID) -> bool:
        stmt = select(exists()).where(self.model.id == uid)
        return await self._session.scalar(stmt)

    async def get_by_ids(self, ids: list[UUID]) -> tuple[EntityT, ...]:
        stmt = select(self.model).where(self.model.id.in_(ids))
        results = await self._session.execute(stmt)
        return [self.data_mapper.from_model(model) for model in results.scalars().all()]
