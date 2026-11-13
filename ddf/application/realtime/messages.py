from typing import Annotated, Literal

import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PositiveInt
from pydantic.alias_generators import to_camel


class Event[T](BaseModel):
    """Публичное событие для доставки realtime-клиентам.

    Отвечает на вопрос: что произошло и какие данные доставляются клиенту?
    """

    model_config = ConfigDict(alias_generator=to_camel, frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: str
    payload: T
    version: PositiveInt = Field(default=1)
    occurred_at: AwareDatetime


class Subscription(BaseModel):
    """На какой ресурс клиент хочет подписаться."""
    topic: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)


class Subscribe(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: uuid.UUID
    type: Literal["subscription.subscribe"]
    payload: Subscription


class Unsubscribe(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    id: uuid.UUID
    type: Literal["subscription.unsubscribe"]
    payload: Subscription


class Reply[T](BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)

    type: str
    reply_to: uuid.UUID | None = None
    payload: T


class ErrorPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, frozen=True)

    code: str = Field(min_length=1, description="Строковый код ошибки в snake_case")
    message: str = Field(min_length=1, description="Человекочитаемое сообщение об ошибке")


SubscriptionCommand = Annotated[Subscribe | Unsubscribe, Field(discriminator="type")]
