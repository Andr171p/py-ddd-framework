from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    redis_url: str = "redis://localhost:6379/0"
    rabbit_url: str = "amqp://guest:guest@localhost:5672/"
    realtime_backend: Literal["redis", "rabbit", "none"] = "redis"
    instance_name: str = "tickets"
    max_subscriptions: int = 64
    denied_tickets: str = ""

    @property
    def denied_ticket_keys(self) -> set[str]:
        return {item.strip() for item in self.denied_tickets.split(",") if item.strip()}
