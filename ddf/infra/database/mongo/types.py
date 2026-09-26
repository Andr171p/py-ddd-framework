from typing import Annotated

import uuid

from pydantic import UUID7, Field

type UUIDPK = Annotated[UUID7, Field(default_factory=uuid.uuid7)]  # type: ignore

__all__ = ["UUIDPK"]
