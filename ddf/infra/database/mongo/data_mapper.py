from typing import Protocol

from ddf.domain.models import Entity

from .mongo_base_model import MongoBaseModel


class DataMapper[EntityT: Entity, ModelT: MongoBaseModel](Protocol):

    def to_model(self, entity: EntityT, /, **kwargs: object) -> ModelT: ...

    def from_model(self, model: ModelT, /, **kwargs: object) -> EntityT: ...
