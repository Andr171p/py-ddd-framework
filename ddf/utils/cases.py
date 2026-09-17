import re


def camel_to_snake_case(name: str) -> str:
    """Приводит camelCase в snake_case, пример: 'itemId' -> 'item_id'."""

    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
