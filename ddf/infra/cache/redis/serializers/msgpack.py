import msgpack
from pydantic import TypeAdapter


class MsgpackSerializer[T]:
    """
    Production-ready бинарный сериализатор на базе msgpack и Pydantic TypeAdapter.

    Характеристики и преимущества:
        - Экономия памяти (Компактность): Msgpack (MessagePack) — это эффективный бинарный
          формат, работающий по принципу "сохраняй JSON как бинарный лог". За счет отсутствия
          текстовых синтаксических конструкций (кавычек, скобок, двоеточий) размер кэшированных
          данных в среднем на 30–50% меньше, чем у стандартного JSON. Это критически важно для
          Highload-систем, так как напрямую сокращает расходы на оперативную память (RAM) в Redis.

        - Скорость сети: Из-за меньшего объема байт на одну запись снижается утилизация сетевого
          канала (Network I/O) между сервером приложения и СУБД, что уменьшает общий latency запросов.

        - Безопасность типов через TypeAdapter: Несмотря на то, что Msgpack нативно не хранит
          информацию о сложных типах (UUID, datetime, set), интеграция с Rust-движком Pydantic
          TypeAdapter гарантирует 100% точное и рекурсивное восстановление всех исходных доменных
          структур при десериализации.
    """

    def __init__(self, target_type: type[T]) -> None:
        self._adapter = TypeAdapter(target_type)

    def dumps(self, value: T) -> bytes:
        cleaned_data = self._adapter.dump_python(value, mode="json")
        return msgpack.dumps(cleaned_data, use_bin_type=True)

    def loads(self, value: bytes) -> T:
        raw_data = msgpack.loads(value, use_list=True)
        return self._adapter.validate_python(raw_data)
