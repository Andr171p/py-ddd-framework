from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from ddf.application.events import EventDispatcher
from ddf.application.exceptions import OperationNotAllowedError
from ddf.application.repositories import Repository
from ddf.application.utils import get_or_raise_not_found
from ddf.domain.models import Entity

from .types import (
    CreateHandler,
    CreateWrapper,
    DeleteHandler,
    DeleteWrapper,
    ReadWrapper,
    UpdateHandler,
    UpdateWrapper,
)


class Crud[
    EntityT: Entity,
    ResponseT: BaseModel,
    CreateT: BaseModel,
    UpdateT: BaseModel,
    CreateOptionsT,
    ReadOptionsT,
    UpdateOptionsT,
    DeleteOptionsT,
]:
    def __init__(
            self,
            repository: Repository[EntityT],
            dispatcher: EventDispatcher,
            to_response: Callable[[EntityT], ResponseT],
            *,
            # handlers:
            create_handler: CreateHandler[EntityT, CreateT, CreateOptionsT] | None = None,
            update_handler: UpdateHandler[EntityT, UpdateT, UpdateOptionsT] | None = None,
            delete_handler: DeleteHandler[EntityT, DeleteOptionsT] | None = None,
            # wrappers:
            create_wrapper: CreateWrapper[EntityT, CreateT, CreateOptionsT] | None = None,
            read_wrapper: ReadWrapper[EntityT, ReadOptionsT] | None = None,
            update_wrapper: UpdateWrapper[EntityT, UpdateT, UpdateOptionsT] | None = None,
            delete_wrapper: DeleteWrapper[EntityT, DeleteOptionsT] | None = None,
    ) -> None:
        self._repository = repository
        self._dispatcher = dispatcher
        self._to_response = to_response

        self._create_handler = create_handler
        self._update_handler = update_handler
        self._delete_handler = delete_handler

        self._create_wrapper = create_wrapper
        self._read_wrapper = read_wrapper
        self._update_wrapper = update_wrapper
        self._delete_wrapper = delete_wrapper

    async def create(
        self, dto: CreateT, options: CreateOptionsT | None = None,
    ) -> ResponseT:
        if self._create_handler is None:
            raise OperationNotAllowedError("Create operation is not supported.")

        async def _base_create(dto_: CreateT, options_: CreateOptionsT | None = None) -> EntityT:
            entity_ = await self._create_handler(dto_, options_)

            await self._repository.create(entity_)
            await self._dispatcher(entity_)

            return entity_

        created = (
            await self._create_wrapper(_base_create, dto, options)
            if self._create_wrapper
            else await _base_create(dto, options)
        )
        return self._to_response(created)

    async def read(self, uid: UUID, options: ReadOptionsT | None = None) -> ResponseT:
        entity = await get_or_raise_not_found(self._repository.read, uid, type[EntityT])

        async def _base_read(entity_: EntityT, options_: ReadOptionsT | None = None) -> EntityT:
            return entity_

        read = (
            await self._read_wrapper(_base_read, entity, options)
            if self._read_wrapper
            else await _base_read(entity, options)
        )

        return self._to_response(read)

    async def update(
        self, uid: UUID, dto: UpdateT, options: UpdateOptionsT | None = None
    ) -> ResponseT:
        if self._update_handler is None:
            raise OperationNotAllowedError("Update operation is not supported.")

        entity = await get_or_raise_not_found(self._repository.read, uid, type[EntityT])

        async def _base_update(
                entity_: EntityT, dto_: UpdateT, options_: UpdateOptionsT | None = None,
        ) -> EntityT:
            handled = await self._update_handler(entity_, dto_, options_)

            await self._repository.update(handled)
            await self._dispatcher(handled)

            return handled

        updated = (
            await self._update_wrapper(_base_update, entity, dto, options)
            if self._update_wrapper
            else await _base_update(entity, dto, options)
        )

        return self._to_response(updated)

    async def delete(self, uid: UUID, options: DeleteOptionsT | None = None) -> None:
        if self._delete_handler is None:
            raise OperationNotAllowedError("Delete operation is not supported.")

        entity = await get_or_raise_not_found(self._repository.read, uid, type[EntityT])

        async def _base_delete(entity_: EntityT, options_: DeleteOptionsT | None) -> EntityT:
            handled = await self._delete_handler(entity_, options_)

            await self._repository.update(handled)
            await self._dispatcher(handled)

            return handled

        if self._delete_wrapper:
            await self._delete_wrapper(_base_delete, entity, options)
            return

        await _base_delete(entity, options)
