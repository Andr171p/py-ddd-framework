from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "<PASSWORD>"
    db: str = "postgres"

    driver: Literal["asyncpg"] = "asyncpg"

    pool_resize: int = 5
    max_overflow: int = 5
    pool_timeout: int = 30
    echo: bool = Field(default=False, description="Для разработки поставить True.")

    @property
    def uri(self) -> str:
        return f"postgresql+{self.driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.db}"
