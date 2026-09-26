from typing import ClassVar

from collections.abc import Mapping, Sequence
from uuid import UUID

from pymongo.asynchronous.collection import AsyncCollection

from ddf.application.dtos import Page, Pagination, QueryDTO, Sort
from ddf.domain.models import Entity

from .data_mapper import DataMapper
from .filters import compile_filter, compile_sort
from .mongo_base_model import MongoBaseModel
from .pagination import paginate


class MongoRepository[EntityT: Entity, ModelT: MongoBaseModel]:
    model: type[ModelT]
    data_mapper: DataMapper[EntityT, ModelT]
    filter_whitelist: ClassVar[Mapping[str, str]]

    def __init__(self, collection: AsyncCollection) -> None:
        self._collection = collection

    async def create(self, entity: EntityT) -> EntityT:
        model = self.data_mapper.to_model(entity)
        await self._collection.insert_one(model.model_dump(by_alias=True))
        return self.data_mapper.from_model(model)

    async def read(self, uid: UUID) -> EntityT | None:
        if (doc := await self._collection.find_one({"_id": uid})) is None:
            return None

        model = self.model.model_validate(doc, by_alias=True)
        return self.data_mapper.from_model(model)

    async def find(
        self,
        pagination: Pagination,
        query: QueryDTO | None = None,
        sort: Sort | None = None,
    ) -> Page[EntityT]:
        mongo_filter = compile_filter(query, allowed_fields=self.filter_whitelist)
        mongo_sort = compile_sort(sort, allowed_fields=self.filter_whitelist)

        page = await paginate(
            self._collection,
            model=self.model,
            filter_=mongo_filter,
            sort=mongo_sort,
            pagination=pagination,
        )
        return page.map(self.data_mapper.from_model)

    async def update(self, entity: EntityT) -> None:
        model = self.data_mapper.to_model(entity)
        doc = model.model_dump(by_alias=True)
        await self._collection.replace_one({"_id": model.id}, doc, upsert=True)

    async def exists(self, uid: UUID) -> bool:
        return await self._collection.count_documents({"_id": uid}, limit=1) > 0

    async def delete(self, uid: UUID) -> None:
        await self._collection.delete_one({"_id": uid})

    async def get_by_ids(self, ids: Sequence[UUID]) -> tuple[EntityT, ...]:
        cursor = self._collection.find({"_id": {"$in": list(ids)}})
        return tuple(
            self.data_mapper.from_model(self.model.model_validate(doc, by_alias=True))
            async for doc in cursor
        )
