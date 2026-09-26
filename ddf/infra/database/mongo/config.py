from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MONGO_")

    host: str = "mongo"
    port: int = 27017
    username: str | None = None
    password: str | None = None
    db: str = "<DB>"

    auth_source: str = "admin"

    @property
    def uri(self) -> str:
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.db}?authSource={self.auth_source}"

        return f"mongodb://{self.host}:{self.port}/{self.db}"
