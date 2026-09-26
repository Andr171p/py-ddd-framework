from typing import ClassVar

from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pymongo import IndexModel

from .types import UUIDPK


class MongoEntityMixin:
    id: UUIDPK = Field(alias="_id")
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: AwareDatetime | None = Field(default=None)


class MongoBaseModel(BaseModel):
    __indexes__: ClassVar[Sequence[IndexModel]] = None  # type: ignore
    __collection_name__: ClassVar[str] = None  # type: ignore

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=to_camel)
