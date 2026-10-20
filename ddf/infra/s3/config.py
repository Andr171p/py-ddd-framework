from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MIN_CHUNK_SIZE = 5 * 1024 * 1024


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="S3_")

    service_name: str = Field(default="s3")
    access_key: str
    secret_key: SecretStr
    endpoint_url: HttpUrl = Field(default="http://localhost:9000")
    region: str = Field(default="us-east-1")
    addressing_style: Literal["auto", "path", "virtual"] = Field(default="path")
    bucket: str = Field(description="Имя бакета")
