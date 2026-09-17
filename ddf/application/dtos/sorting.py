from typing import Annotated, Literal

from fastapi import Depends, Query
from pydantic import BaseModel

type SortDirection = Literal["asc", "desc"]


class Sort(BaseModel):
    field: str = Query(description="Поле по которому выполняется сортировка")
    direction: SortDirection = Query(default="asc", description="Направление сортировки")


def parse_sort_query_param(param: str | None) -> Sort:
    """Парсит query-параметр сортировки."""

    cleaned = param.strip()
    if not cleaned:
        raise ValueError("Sort query param cannot be empty.")

    if cleaned.startswith("-"):
        field = cleaned[1:]
        direction: SortDirection = "desc"

    elif ":" in cleaned:
        field, raw_direction = cleaned.split(":", maxsplit=1)
        direction = raw_direction.lower()

    else:
        field = cleaned
        direction = "asc"

    if not field:
        raise ValueError("Sort field cannot be empty.")

    if direction not in ("asc", "desc"):
        raise ValueError(f"Invalid sort direction: {direction!r}." "Expected 'asc' or 'desc'.")

    return Sort(field=field, direction=direction)


Sorting = Annotated[Sort, Depends()]


__all__ = ["Sort", "SortDirection", "Sorting", "parse_sort_query_param"]
