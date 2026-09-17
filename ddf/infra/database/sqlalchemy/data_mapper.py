from typing import Protocol

from ddf.domain.models import Entity

from .base import Base


class DataMapper[EntityT: Entity, ModelT: Base](Protocol):

    def to_model(self, entity: EntityT) -> ModelT: ...

    def from_model(self, model: ModelT) -> EntityT: ...
