from typing import Annotated

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from .operators import ComparisonOperator, LogicOperator
from .types import RichJsonValue


class DslNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Condition(DslNode):
    """Условие фильтрации по одному полю."""

    field: str = Field(min_length=1, max_length=64, description="Имя поля")
    op: ComparisonOperator = Field(description="Оператор сравнения")
    value: RichJsonValue | None = Field(default=None, description="Значение для сравнения")


class Group(DslNode):
    """Группа условий, объединённых логическим оператором."""

    op: LogicOperator = Field(description="Логический оператор")
    filters: tuple["Expression", ...] = Field(description="Условия группы")


class Negation(DslNode):
    """Отрицание сложной группы (логика Де Моргана)."""

    filter_: "Expression" = Field(alias="filter", description="Условие которое нужно отрицать")


class Search(DslNode):
    """Полнотекстовый поиск."""

    query: str = Field(min_length=1, max_length=256, description="Поисковый запрос")


def get_expression_type(value: object) -> str | None:
    if isinstance(value, Condition):
        return "condition"

    if isinstance(value, Group):
        return "group"

    if isinstance(value, Negation):
        return "negation"

    if isinstance(value, Search):
        return "search"

    if isinstance(value, dict):
        markers = {
            "field": "condition",
            "filters": "group",
            "filter": "negation",
            "query": "search",
        }
        matches = [kind for key, kind in markers.items() if key in value]
        return matches[0] if len(matches) == 1 else None

    return None


type Expression = Annotated[
    Annotated[Condition, Tag("condition")]
    | Annotated[Group, Tag("group")]
    | Annotated[Negation, Tag("negation")]
    | Annotated[Search, Tag("search")],
    Discriminator(get_expression_type),
]

__all__ = ["Condition", "Expression", "Group", "Negation", "Search"]
