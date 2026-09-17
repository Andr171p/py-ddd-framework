from typing import Any

from collections.abc import Callable, Collection, Mapping

from sqlalchemy import ColumnElement, UnaryExpression, and_, not_, or_

from ddf.application.dsl import (
    Condition,
    Expression,
    Group,
    Negation,
    Search,
)
from ddf.utils.cases import camel_to_snake_case

from .base import Base
from .types import SearchFunc

type SortFunc = Callable[[ColumnElement[Any]], UnaryExpression[Any]]


def _get_column[ModelT: Base](
    model: type[ModelT],
    field: str,
    allowed_fields: Collection[str],
) -> ColumnElement[Any]:
    if field not in allowed_fields:
        raise ValueError(f"Unknown filter field: '{field}'.")

    field_name = camel_to_snake_case(field)

    try:
        return getattr(model, field_name)
    except AttributeError:
        raise ValueError(f"Filter field '{field}' is not supported by model.") from None


def compile_filter[ModelT: Base](
    model: type[ModelT],
    expression: Expression,
    allowed_fields: Collection[str],
    search: SearchFunc | None = None,
) -> ColumnElement[bool]:
    """
    Компилирует абстрактный DSL-фильтр в выражение SQLAlchemy.

    Функция является точкой входа для компиляции фильтров. Она рекурсивно
    разбирает структуру фильтра (условие, логическая группа или отрицание)
    и преобразует её в соответствующий объект `ColumnElement` из SQLAlchemy.
    """

    if isinstance(expression, Condition):
        return _compile_condition(model, expression, allowed_fields)

    if isinstance(expression, Search) and search is None:
        raise ValueError("Full-text search is not supported.")

    if isinstance(expression, Group):
        return _compile_group(expression, allowed_fields, search)

    if isinstance(expression, Negation):
        return not_(compile_filter(expression.filter_, allowed_fields, search))

    raise ValueError(f"Unsupported filter type: {type(expression)}")


def _compile_condition[ModelT: Base](  # noqa: C901, PLR0911
    model: type[ModelT],
    condition: Condition,
    allowed_fields: Collection[str],
) -> ColumnElement[bool]:
    """Компилирует одиночное атомарное условие (Condition) в выражение SQLAlchemy.

    Функция маппит строковые операторы DSL (например, `"$eq"`, `"$in"`, `"$ilike"`)
    в соответствующие операторы сравнения или методы колонок SQLAlchemy.
    """

    column = _get_column(model, condition.field, allowed_fields)

    match condition.op:
        case "$eq":
            return column == condition.value

        case "$ne":
            return column != condition.value

        case "$gt":
            return column > condition.value

        case "$gte":
            return column >= condition.value

        case "$lt":
            return column < condition.value

        case "$lte":
            return column <= condition.value

        case "$in":
            _ensure_list_value(condition)
            return column.in_(condition.value)

        case "$nin":
            _ensure_list_value(condition)
            return column.not_in(condition.value)

        case "$like":
            return column.like(_ensure_str_value(condition))

        case "$ilike":
            return column.ilike(_ensure_str_value(condition))

        case "$isNull":
            return column.is_(None)

        case "$isNotNull":
            return column.is_not(None)

    raise ValueError(f"Unsupported filter operator: '{condition.op}'")


def _compile_group(
    group: Group,
    fields: Mapping[str, ColumnElement[Any]],
    search: SearchFunc | None,
) -> ColumnElement[bool]:
    """Компилирует группу фильтров (Group) объединяя их логическим оператором AND или OR.

    Функция рекурсивно вызывает `compile_filter` для каждого дочернего фильтра
    в группе, а затем оборачивает их в SQLAlchemy-функции `and_()` или `or_()`.
    """

    filters = tuple(compile_filter(filter_, fields, search) for filter_ in group.filters)

    if not filters:
        raise ValueError("Filter group cannot be empty.")

    match group.op:
        case "$and":
            return and_(*filters)

        case "$or":
            return or_(*filters)

    raise ValueError(f"Unsupported logic operator: '{group.op}'")


def _ensure_list_value(condition: Condition) -> list[Any]:
    """
    Проверяет, что значение в условии является списком.
    Используется для валидации значений операторов `"$in"` и `"$nin"`.
    """
    if not isinstance(condition.value, list):
        raise ValueError(f"Operator '{condition.op}' expects a list value.")

    return condition.value


def _ensure_str_value(condition: Condition) -> str:
    """
    Проверяет, что значение в условии является строкой.
    Используется для валидации значений операторов `"$like"` и `"$ilike"`.
    """
    if not isinstance(condition.value, str):
        raise ValueError(f"Operator '{condition.op}' expects a string value.")

    return condition.value


__all__ = ["compile_filter"]
