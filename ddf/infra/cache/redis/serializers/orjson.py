import orjson
from pydantic import TypeAdapter


class OrJsonSerializer[T]:
    """
    Высокопроизводительный текстовый сериализатор на базе orjson и Pydantic TypeAdapter.

    Характеристики и преимущества:
        - Скорость работы: orjson является одной из самых быстрых библиотек для работы с JSON
          в Python. Она написана на Rust и значительно превосходит по скорости стандартный
          модуль `json` и `ujson` за счет оптимизированной сериализации примитивов.

        - Читаемость данных: На выходе формируется валидная UTF-8 JSON-строка (в байтах).
          Это делает кэш прозрачным для человека — данные в Redis легко читать, анализировать
          и отлаживать глазами через консоль (CLI) или графические утилиты (Redis Insight).

        - Нативная поддержка типов: orjson из коробки эффективно сериализует специфичные типы,
          такие как dataclasses, UUID, datetime и Enum, снижая накладные расходы на конвертацию.
    """

    def __init__(self, target_type: type[T]) -> None:
        self._adapter = TypeAdapter(target_type)

    def dumps(self, value: T) -> bytes:
        """
        Сначала превращаем объект в python-примитивы с учетом правил Pydantic,
        затем orjson моментально упаковывает их в байты.
        """
        plain_obj = self._adapter.dump_python(value, mode="json")
        return orjson.dumps(plain_obj)

    def loads(self, value: bytes) -> T:
        """orjson быстро разбирает байты в примитивы, TypeAdapter восстанавливает исходную структуру."""
        plain_obj = orjson.loads(value)
        return self._adapter.validate_python(plain_obj)
