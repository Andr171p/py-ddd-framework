from typing import Literal

# Логические операторы
type LogicOperator = Literal["$and", "$or"]

# Операторы сравнения для одиночных значений (скалярные)
type ScalarOperator = Literal["$eq", "$ne", "$gt", "$gte", "$lt", "$lte"]

# Операторы сопоставления строк (текстовые)
type StrOperator = Literal["$like", "$ilike"]

# Операторы для работы с массивами/списками/коллекциями
type ListOperator = Literal["$in", "$nin"]

# Операторы для проверки на пустоту (унарные)
type NullOperator = Literal["$isNull", "$isNotNull"]

# Собираем операторы фильтрации (все, кроме логических)
type ComparisonOperator = ScalarOperator | StrOperator | ListOperator | NullOperator

# Все DSL операторы
type AnyOperator = LogicOperator | ComparisonOperator

__all__ = [
    "AnyOperator",
    "ComparisonOperator",
    "ListOperator",
    "LogicOperator",
    "NullOperator",
    "ScalarOperator",
    "StrOperator",
]
