import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus

import aiohttp
import jwt
import jwt.algorithms
import orjson
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from .config import KeycloakConfig
from .exceptions import InvalidTokenError, KeycloakUnavailableError

_NEGATIVE_INF = float("-inf")
_PRIVATE_RSA_FIELDS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})
_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class _SigningKey:
    public_key: RSAPublicKey
    algorithms: frozenset[str]


def _parse_key(raw: object, config: KeycloakConfig) -> tuple[str, _SigningKey] | None:
    if not isinstance(raw, dict):
        return None

    kid = raw.get("kid")

    if not isinstance(kid, str) or not kid or raw.get("kty") != "RSA":
        return None

    if any(field in raw for field in _PRIVATE_RSA_FIELDS):
        return None

    if raw.get("use") not in (None, "sig"):
        return None

    if (key_ops := raw.get("key_ops")) is not None and (
        not isinstance(key_ops, list)
        or not all(isinstance(item, str) for item in key_ops)
        or "verify" not in key_ops
    ):
        return None

    if (declared_alg := raw.get("alg")) is not None:
        if not isinstance(declared_alg, str) or declared_alg not in config.algorithms:
            return None

        algorithms = frozenset({declared_alg})
    else:
        algorithms = frozenset(config.algorithms)

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(raw)
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        return None

    if not isinstance(public_key, RSAPublicKey) or public_key.key_size < config.min_rsa_key_bits:
        return None

    return kid, _SigningKey(public_key=public_key, algorithms=algorithms)


def _parse_jwks(document: object, config: KeycloakConfig) -> dict[str, _SigningKey]:
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise ValueError("Invalid JWKS document")

    raw_keys = document["keys"]

    if len(raw_keys) > config.max_jwks_keys:
        raise ValueError("JWKS contains too many keys")

    keys: dict[str, _SigningKey] = {}

    for raw in raw_keys:
        parsed = _parse_key(raw, config)

        if parsed is None:
            continue

        kid, signing_key = parsed

        if kid in keys:
            raise ValueError("JWKS contains duplicate signing key IDs")

        keys[kid] = signing_key

    if not keys:
        raise ValueError("JWKS contains no usable signing keys")

    return keys


def _select_algorithm(key: _SigningKey, algorithm: str) -> RSAPublicKey:
    """Гарантирует, что для данного ключа разрешено использование запрашиваемого алгоритма."""

    if algorithm not in key.algorithms:
        raise InvalidTokenError("Signing algorithm is not allowed for this key")

    return key.public_key


class KeycloakJwksClient:
    """Асинхронный JWKS клиент с локальным кешем и поддержкой ротацией ключей.

    Что реализует:
        - Ленивая инициализация HTTP сессии;
        - Single-flight JWKS ротация;
        - Monotonic cache TTL
        - период ожидания повторной попытки в случае ошибки;
        - Атомарная замена JWKS;
        - мягкое закрытие сессии.

    Используется в рамках одного цикла событий asyncio.
    """

    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config

        self._session: aiohttp.ClientSession | None = None

        self._session_lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()

        self._keys: dict[str, _SigningKey] = {}

        self._loaded_at = _NEGATIVE_INF
        self._retry_after = _NEGATIVE_INF
        self._unknown_kid_refresh_after = _NEGATIVE_INF

    async def _is_fresh(self, now: float) -> bool:
        """Проверьте, является ли текущий снимок JWKS действительным."""
        return bool(self._keys) and now - self._loaded_at < self._config.jwks_cache_ttl

    async def _fetch_keys(self) -> dict[str, _SigningKey]:
        """Получает и проверяет полный снимок JWKS."""

        headers = {"Accept": "application/json"}

        try:
            async with (
                self._get_session() as session,
                session.get(str(self._config.jwks_url), allow_redirects=True, headers=headers) as response,
            ):
                if response.status != HTTPStatus.OK:
                    raise KeycloakUnavailableError("Unable to fetch Keycloak signing keys")

                if (
                    response.content_length is not None
                    and response.content_length > self._config.max_jwks_bytes
                ):
                    raise KeycloakUnavailableError("JWKS document exceeds size limit")

                data = bytearray()

                async for chunk in response.content.iter_chunked(_CHUNK_SIZE):
                    data.extend(chunk)

                    if len(data) > self._config.max_jwks_bytes:
                        raise KeycloakUnavailableError("JWKS document exceeds size limit")

        except (aiohttp.ClientError, TimeoutError) as exc:
            raise KeycloakUnavailableError("Unable to fetch Keycloak signing keys") from exc

        try:
            document = orjson.loads(data)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise KeycloakUnavailableError("Keycloak returned invalid signing keys") from exc
        else:
            return _parse_jwks(document, self._config)

    async def get_key(self, kid: str, algorithm: str) -> RSAPublicKey:
        """Получает подпись ключа по его идентификатору и алгоритму.

        Если ключ найден в кэше, он возвращается без захвата блокировки обновления.

        В случае промаха кеша:
         1. Накладывается лок на обновление.
         2. Выполняется повторная проверка кэша.
         3. Применяются ограничения по частоте обновлений (cooldowns).
         4. Выполняется получение и проверка нового снимка JWKS.
         5. Кэшированные ключи заменяются атомарно.
        """

        if not isinstance(kid, str) or not kid:
            raise InvalidTokenError("Missing signing key ID")

        if algorithm not in self._config.algorithms:
            raise InvalidTokenError("Unsupported signing algorithm")

        now = time.monotonic()

        if self._is_fresh(now) and (key := self._keys.get(kid)) is not None:
            return _select_algorithm(key, algorithm)

        async with self._refresh_lock:
            now = time.monotonic()
            fresh = self._is_fresh(now)

            # Другая корутина уже могла обновить JWKS.
            if fresh and (key := self._keys.get(kid)) is not None:
                return _select_algorithm(key, algorithm)

            if now < self._retry_after:
                raise KeycloakUnavailableError("JWKS refresh is temporarily unavailable")

            if fresh:
                if now < self._unknown_kid_refresh_after:
                    raise InvalidTokenError("Unknown signing key")

                self._unknown_kid_refresh_after = now + self._config.jwks_refresh_cooldown

            try:
                keys = await self._fetch_keys()
            except KeycloakUnavailableError:
                self._retry_after = time.monotonic() + self._config.jwks_refresh_cooldown
                raise

            now = time.monotonic()

            self._keys = keys
            self._loaded_at = now
            self._retry_after = _NEGATIVE_INF

            if (key := keys.get(kid)) is None:
                self._unknown_kid_refresh_after = now + self._config.jwks_refresh_cooldown

                raise InvalidTokenError("Unknown signing key")

            return _select_algorithm(key, algorithm)

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        """Ленивое получение общей HTTP сессии."""

        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self._config.timeout),
                    connector=aiohttp.TCPConnector(limit=self._config.pool_limit),
                    cookie_jar=aiohttp.DummyCookieJar(),
                    trust_env=False,
                )

            session = self._session

        yield session

    async def close(self) -> None:
        """Закрывает общую HTTP сессию после завершения активных запросов."""

        async with self._session_lock:
            session = self._session
            self._session = None

        if session is not None:
            await session.close()


__all__ = ["KeycloakJwksClient"]
