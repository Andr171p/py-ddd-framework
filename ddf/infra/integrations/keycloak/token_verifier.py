from typing import Any

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import jwt

from .config import KeycloakConfig
from .exceptions import InvalidTokenError
from .jwks import KeycloakJwksClient

_REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud", "sub")


def _get_signing_header(token: str, allowed_algorithms: tuple[str, ...]) -> tuple[str, str]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid token header") from exc

    if "crit" in header or header.get("b64") is False:
        raise InvalidTokenError("Unsupported JOSE header")

    kid, algorithm = header.get("kid"), header.get("alg")

    if not isinstance(kid, str) or not kid:
        raise InvalidTokenError("Missing signing key ID")

    if not isinstance(algorithm, str) or algorithm not in allowed_algorithms:
        raise InvalidTokenError("Unsupported signing algorithm")

    return kid, algorithm


def _parse_audience(value: object) -> tuple[str, ...]:
    if isinstance(value, str) and value:
        return (value,)

    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, str) and item for item in value)
    ):
        return tuple(value)

    raise InvalidTokenError("Invalid audience claim")


def _validate_numeric_dates(claims: dict) -> None:
    for name in ("exp", "iat", "nbf"):
        if name not in claims:
            continue

        value = claims[name]

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise InvalidTokenError(f"Invalid {name} claim")


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    subject: str
    issuer: str
    audience: tuple[str, ...]
    claims: Mapping[str, Any]


class KeycloakTokenVerifier:
    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._jwks_client = KeycloakJwksClient(config)

    async def verify(self, token: str) -> VerifiedToken:
        """Сверяет access токен и возвращает его claims."""

        if (
            not isinstance(token, str)
            or not token
            or not token.isascii()
            or len(token) > self._config.max_token_bytes
        ):
            raise InvalidTokenError("Invalid access token")

        kid, algorithm = _get_signing_header(token, self._config.algorithms)
        key = await self._jwks_client.get_key(kid, algorithm)

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=self._config.algorithms,
                audience=self._config.audience,
                issuer=str(self._config.issuer_url).rstrip("/"),
                leeway=self._config.clock_skew,
                options={
                    "require": list(_REQUIRED_CLAIMS),
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
            raise InvalidTokenError("Invalid access token") from exc

        subject = claims.get("sub")

        if not isinstance(subject, str) or not subject:
            raise InvalidTokenError("Invalid subject claim")

        issuer = claims.get("iss")

        if not isinstance(issuer, str) or not issuer:
            raise InvalidTokenError("Invalid issuer claim")

        audience = _parse_audience(claims.get("aud"))

        if (
            self._config.expected_token_type is not None
            and claims.get("typ") != self._config.expected_token_type
        ):
            raise InvalidTokenError("Unexpected token type")

        _validate_numeric_dates(claims)

        return VerifiedToken(
            subject=subject,
            issuer=issuer,
            audience=audience,
            claims=MappingProxyType(claims),
        )

    async def close(self) -> None:
        await self._jwks_client.close()


__all__ = ["KeycloakTokenVerifier", "VerifiedToken"]
