
from typing import Literal

from pydantic import AnyHttpUrl, Field, NonNegativeFloat, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_")

    issuer_url: AnyHttpUrl = Field(description="URL издателя токенов (Keycloak Realm URL)")
    audience: str = Field(min_length=1, description="Идентификатор (аудитория) текущего API")
    jwks_url: AnyHttpUrl | None = Field(
        default=None,
        description="URL эндпоинта Keycloak с публичными ключами (JWKS)",
    )

    algorithms: tuple[Literal["RS256", "RS384", "RS512"], ...] = Field(
        default=("RS256",),
        min_length=1,
        description="Разрешенные алгоритмы асимметричного шифрования",
    )
    expected_token_type: Literal["Bearer"] = Field(default="Bearer", description="Ожидаемый формат токена")

    jwks_cache_ttl: PositiveFloat = Field(
        default=300.0,
        description="Время жизни кэша публичных ключей JWKS в секундах",
    )
    jwks_refresh_cooldown: PositiveFloat = Field(
        default=5.0,
        description="Интервал в секундах между принудительными обновлениями ключей",
    )

    clock_skew: NonNegativeFloat = Field(
        default=5.0,
        le=60,
        description="Допустимая погрешность часов сервера в секундах при проверке времени жизни токена",
    )
    timeout: PositiveFloat = Field(default=10.0, description="Таймаут в секундах на сетевые запросы")
    pool_limit: PositiveInt = Field(default=20, description="Максимальное количество соединений в пуле")

    max_token_bytes: PositiveInt = 32 * 1024
    max_jwks_bytes: PositiveInt = 256 * 1024
    max_jwks_keys: PositiveInt = 128
    min_rsa_key_bits: int = Field(default=2048, ge=2048,)
