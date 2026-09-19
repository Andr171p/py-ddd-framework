from pydantic import Field, NonNegativeFloat
from pydantic_settings import BaseSettings, SettingsConfigDict


class OutboxWorkerConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OUTBOX_WORKER_")

    poll_interval: NonNegativeFloat = Field(
        default=1.0,
        description="Интервал (в секундах) между плановыми проверками таблицы outbox при наличии сообщений",
    )
    error_interval: NonNegativeFloat = Field(
        default=5.0,
        description="Время ожидания (в секундах) перед повторной попыткой после возникновения ошибки",
    )
    notification_timeout: NonNegativeFloat = Field(
        default=30.0,
        description=(
            "Максимальное время ожидания (в секундах) уведомления NOTIFY из PostgreSQL "
            "перед принудительным опросом"
        ),
    )
