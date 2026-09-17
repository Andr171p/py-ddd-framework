from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RABBIT_")

    host: str = "rabbit"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtualhost: str = "/"

    exchange: str = Field(description="Основной exchange для приложения")

    heartbeat: int = 30
    connection_timeout: float = 10.0

    @property
    def uri(self) -> str:
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.virtualhost.lstrip('/')}"
