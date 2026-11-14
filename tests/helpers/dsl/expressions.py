from typing import Any


def condition(field: str, op: str, value: Any = None, *, with_value: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {"field": field, "op": op}
    if with_value:
        payload["value"] = value
    return payload


def group(op: str, *filters: dict[str, Any]) -> dict[str, Any]:
    return {"op": op, "filters": list(filters)}


def negate(expression: dict[str, Any]) -> dict[str, Any]:
    return {"filter": expression}


def search(query: str) -> dict[str, Any]:
    return {"query": query}
