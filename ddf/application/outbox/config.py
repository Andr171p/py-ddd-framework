from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

_MAX_BATCH_SIZE = 500


class OutboxConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OUTBOX_")

    batch_size: PositiveInt = Field(
        default=100,
        le=_MAX_BATCH_SIZE,
        description="Сколько событий обработается за один вызов",
    )
    max_attempts: PositiveInt = Field(
        default=5,
        le=10,
        description="Максимальное количество попыток обработки",
    )

    concurrency_enable: bool = Field(
        default=False,
        description="Использовать ли параллельную отправку сообщений",
    )
    max_concurrency: PositiveInt = Field(
        default=10,
        le=_MAX_BATCH_SIZE,
        description="Максимальное количество одновременно публикуемых событий",
    )
