from typing import Any, ClassVar

from dataclasses import dataclass
from http import HTTPStatus


@dataclass
class DomainError(Exception):
    """Базовое доменное исключение - от него наследуются все доменные исключения."""

    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: ClassVar[str] = "INTERNAL_SERVER_ERROR"

    message: str | None = None
    details: dict[str, Any] | list[Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class InvariantViolationError(DomainError):
    status_code = HTTPStatus.CONFLICT
    error_code = "INVARIANT_VIOLATION"


class InvalidStateError(DomainError):
    status_code = HTTPStatus.CONFLICT
    error_code = "INVALID_STATE"
