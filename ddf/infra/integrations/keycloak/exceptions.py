
class KeycloakVerificationError(Exception):
    """Базовое исключение для локальной верификации access токена Keycloak."""


class InvalidTokenError(KeycloakVerificationError):
    """Предоставленный токен недействителен или не принимается данным API."""


class KeycloakUnavailableError(KeycloakVerificationError):
    """Не удается получить или обновить доверенные ключи подписи."""
