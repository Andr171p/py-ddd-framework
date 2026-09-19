from typing import Annotated, Any

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import TEXT, ColumnElement, DateTime, String, UnaryExpression
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import mapped_column

type SortFunc = Callable[[ColumnElement[Any]], UnaryExpression[Any]]
type SearchFunc = Callable[[str], ColumnElement[bool]]

type Str255 = Annotated[str, mapped_column(String(255))]
type StrUnique = Annotated[str, mapped_column(unique=True)]
type StrNull = Annotated[str | None, mapped_column(nullable=True)]
type TextNull = Annotated[str | None, mapped_column(TEXT, nullable=True)]

type UuidUnique = Annotated[UUID, mapped_column(PG_UUID[UUID](as_uuid=True), unique=True)]
type UuidNull = Annotated[UUID | None, mapped_column(PG_UUID[UUID](as_uuid=True), nullable=True)]
type UuidPk = Annotated[UUID, mapped_column(PG_UUID[UUID](as_uuid=True), primary_key=True)]

type DatatimeTz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
type DatetimeTzNull = Annotated[
    datetime | None,
    mapped_column(DateTime(timezone=True), nullable=True),
]

__all__ = [
    "DatatimeTz",
    "DatetimeTzNull",
    "SearchFunc",
    "SortFunc",
    "Str255",
    "StrNull",
    "StrUnique",
    "TextNull",
    "UuidNull",
    "UuidPk",
    "UuidUnique",
]
