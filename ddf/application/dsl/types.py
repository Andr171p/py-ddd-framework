from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime

type ScalarValue = UUID | AwareDatetime | Decimal | str | int | float | bool | None
type RichJsonValue = (
    ScalarValue
    | set[RichJsonValue]
    | list[RichJsonValue]
    | tuple[RichJsonValue, ...]
)

__all__ = ["RichJsonValue"]
