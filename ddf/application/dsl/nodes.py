from pydantic import BaseModel, Field

from .operators import ComparisonOperator, LogicOperator
from .types import RichJsonValue


class Condition(BaseModel):
    """Условие фильтрации по одному полю."""

    field: str = Field(description="Имя поля")
    op: ComparisonOperator = Field(description="Оператор сравнения.")
    value: RichJsonValue | None = Field(default=None, description="Значение для сравнения.")


class Group(BaseModel):
    """Группа условий, объединённых логическим оператором."""

    op: LogicOperator = Field(description="Логический оператор.")
    filters: tuple["Expression", ...] = Field(description="Условия группы.")


class Negation(BaseModel):
    """Отрицание сложной группы (логика Де Моргана)."""

    filter_: "Expression" = Field(alias="filter", description="Условие которое нужно отрицать.")


class Search(BaseModel):
    """Полнотекстовый поиск."""

    query: str = Field(description="Поисковый запрос.")


type Expression = Condition | Group | Negation | Search

__all__ = ["Condition", "Expression", "Group", "Negation", "Search"]
