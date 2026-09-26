from __future__ import annotations

from typing import Any

import re
from collections.abc import Mapping

from ddf.application.dsl import Condition, Expression, Group, Negation
from ddf.application.dtos import Sort


def compile_sort(sort: Sort | None, *, allowed_fields: Mapping[str, str]) -> list[tuple[str, int]]:
    if sort is None:
        return [("_id", -1)]

    field = _resolve_field(sort.field, allowed_fields)
    direction = 1 if sort.direction == "asc" else -1
    result = [(field, direction)]

    if field != "_id":
        result.append(("_id", direction))

    return result


def compile_filter(expression: Expression, *, allowed_fields: Mapping[str, str]) -> dict[str, Any]:
    """
    Компилирует абстрактный DSL-фильтр в Mongo JSON фильтр.

    Функция является точкой входа для компиляции фильтров. Она рекурсивно
    разбирает структуру фильтра (условие, логическая группа или отрицание)
    и преобразует её в соответствующий JSON фильтр.
    """

    match expression:
        case Condition():
            return _compile_condition(expression, fields=allowed_fields)

        case Group():
            return _compile_group(expression, fields=allowed_fields)

        case Negation():
            return {"$nor": [compile_filter(expression.filter_, allowed_fields=allowed_fields)]}

    raise TypeError(f"Unsupported filter: {type(expression).__name__}.")


def _compile_group(group: Group, *, fields: Mapping[str, str]) -> dict[str, Any]:
    filters = [compile_filter(filter, allowed_fields=fields) for filter in group.filters]

    if not filters:
        return {}

    if len(filters) == 1:
        return filters[0]

    operator = "$and" if group.op == "and" else "$or"
    return {operator: filters}


def _compile_condition(condition: Condition, *, fields: Mapping[str, str]) -> dict[str, Any]:  # noqa: C901, PLR0911
    """Компилирует одиночное атомарное условие (Condition) в MongoDB JSON фильтр."""

    field = _resolve_field(condition.field, fields)
    value = condition.value

    match condition.op:
        case "$eq":
            return {field: value}

        case "$ne":
            return {field: {"$ne": value}}

        case "$gt":
            return {field: {"$gt": value}}

        case "$gte":
            return {field: {"$gte": value}}

        case "$lt":
            return {field: {"$lt": value}}

        case "$lte":
            return {field: {"$lte": value}}

        case "$in":
            return {field: {"$in": list(value)}}

        case "$nin":
            return {
                field: {"$nin": list(value)}}

        case "isNull":
            return {field: {"$type": 10}}

        case "$isNotNull":
            return {field: {"$exists": True, "$ne": None}}

        case "like":
            return {
                field: {
                    "$regex": _compile_like_pattern(str(value)),
                },
            }

        case "ilike":
            return {
                field: {
                    "$regex": _compile_like_pattern(str(value)),
                    "$options": "i",
                },
            }

    raise ValueError(f"Unsupported Mongo operator: {condition.op!r}.")


def _compile_like_pattern(pattern: str) -> str:
    """
    Компилирует SQL LIKE pattern в Mongo regex.

    % -> .*
    _ -> .

    Остальные regex-символы экранируются.
    """

    parts: list[str] = []

    for char in pattern:
        if char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))

    return f"^{''.join(parts)}$"


def _resolve_field(field: str, fields: Mapping[str, str]) -> str:
    if field not in fields:
        raise ValueError(f"Unknown query field: {field!r}.")

    return fields[field]


__all__ = ["compile_filter", "compile_sort"]
