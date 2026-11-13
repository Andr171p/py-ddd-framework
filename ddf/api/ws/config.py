from datetime import timedelta

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

from ddf.application.limits import ConcurrencyPolicy
from ddf.application.realtime import OverflowPolicy
from ddf.ratelimit import FixedWindowPolicy


class WsAdmissionConfig(BaseModel):
    connect_limit: PositiveInt = Field(default=10, description="")
    connect_window: timedelta = Field(default=timedelta(minutes=1), gt=timedelta(0))

    max_concurrent_connections: PositiveInt = Field(
        default=5,
        description="Максимальное кол-во параллельных соединений",
    )
    lease_ttl: timedelta = Field(default=timedelta(seconds=60), gt=timedelta(seconds=3))

    @property
    def connect_rate_policy(self) -> FixedWindowPolicy:
        return FixedWindowPolicy(limit=self.connect_limit, window=self.connect_window)

    @property
    def concurrency_policy(self) -> ConcurrencyPolicy:
        return ConcurrencyPolicy(limit=self.max_concurrent_connections, lease_ttl=self.lease_ttl)


class WsSubscriptionConfig(BaseModel):
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

    admission: WsAdmissionConfig = Field(default_factory=WsAdmissionConfig)
    subscription: WsSubscriptionConfig = Field(default_factory=WsSubscriptionConfig)
