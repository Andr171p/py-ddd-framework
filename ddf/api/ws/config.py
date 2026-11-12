from datetime import timedelta

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from ddf.application.realtime import OverflowPolicy
from ddf.ratelimit import FixedWindowPolicy


class WsSubscriptionConfig(BaseModel):
    model_config = SettingsConfigDict(env_prefix="WS_SUBSCRIPTION_")

    max_consecutive_invalid_commands: PositiveInt = Field(
        default=5,
        description="Максимальное количество последовательных недопустимых команд",
    )
    authorization_timeout: PositiveFloat = Field(default=5.0)

    command_limit: PositiveInt = Field(default=120)
    command_window: timedelta = Field(default_factory=lambda: timedelta(minutes=1))

    @property
    def command_rate_policy(self) -> FixedWindowPolicy:
        return FixedWindowPolicy(limit=self.command_limit, window=self.command_window)


class WsConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WS_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    queue_size: PositiveInt = Field(default=128, description="Размер локальной очереди (backpressure)")
    overflow: OverflowPolicy = Field(
        default=OverflowPolicy.DISCONNECT,
        description="Политика переполнения локальной очереди",
    )

    max_incoming_bytes: PositiveInt = Field(
        default=16_384,
        description="Максимальный размер входящего сообщения",
    )

    send_timeout: PositiveFloat = Field(default=15.0, description="Таймаут отправки сообщения")
    close_timeout: PositiveFloat = Field(default=1.0, description="Таймаут для закрытия соединения")

    subscription: WsSubscriptionConfig = Field(default_factory=WsSubscriptionConfig)
