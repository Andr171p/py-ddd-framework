from typing import Any, ClassVar

from dataclasses import dataclass
from http import HTTPStatus


@dataclass
class ApplicationError(Exception):
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: ClassVar[str] = "internal_server_error"

    message: str | None = None
    details: dict[str, Any] | list[Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class NotFoundError(ApplicationError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "not_found"


class OperationNotAllowedError(ApplicationError):
    status_code = HTTPStatus.METHOD_NOT_ALLOWED
    error_code = "operation_not_allowed"


class AlreadyExistsError(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    error_code = "already_exists"


class UniqueConstraintViolationError(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    error_code = "unique_constraint_violation"
