from typing import Any, ClassVar

from dataclasses import dataclass
from http import HTTPStatus


@dataclass
class ApplicationError(Exception):
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: ClassVar[str] = "INTERNAL_SERVER_ERROR"

    message: str | None = None
    details: dict[str, Any] | list[Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class NotFoundError(ApplicationError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "NOT_FOUND"


class OperationNotAllowedError(ApplicationError):
    status_code = HTTPStatus.METHOD_NOT_ALLOWED
    error_code = "OPERATION_NOT_ALLOWED"


class AlreadyExistsError(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    error_code = "ALREADY_EXISTS"
