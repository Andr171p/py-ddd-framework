# Установка

## Требования

DDF использует современный синтаксис обобщений Python (`class Cache[T]`) и генерацию UUIDv7 из стандартной библиотеки. Нужен **Python 3.14 или новее**.

Проект управляет зависимостями через [uv](https://docs.astral.sh/uv/). Его можно установить один раз согласно официальной инструкции.

## Подключение к проекту

Пока DDF развивается внутри этого репозитория, удобнее добавить его как зависимость по пути или Git-зависимость в проект-потребитель. Для работы в самом репозитории достаточно:

```shell
uv sync --all-groups
```

Основной набор уже включает FastAPI, Pydantic, Redis, `orjson` и MessagePack. Необязательные интеграции устанавливаются явно:

```shell
# SQLAlchemy 2 и asyncpg
uv sync --extra sqlalchemy

# FastStream с RabbitMQ
uv sync --extra rabbit
```

В будущем, после публикации пакета, установка будет выглядеть как `uv add py-ddd-framework[sqlalchemy]`.

## Локальная документация

Зависимости сайта вынесены в отдельную группу `docs`, поэтому не попадут в runtime-окружение приложения:

```shell
uv sync --group docs
uv run --group docs mkdocs serve
```

Сайт будет доступен по адресу, который выведет MkDocs (обычно `http://127.0.0.1:8000`). Для проверяемой статической сборки:

```shell
uv run --group docs mkdocs build --strict
```

!!! note "Почему отдельная группа"

    Генератор сайта нужен CI и авторам документации, но не production-приложению. `dependency-groups.docs` сохраняет этот инструмент в lock-файле, не расширяя набор зависимостей пакета.

## Быстрая проверка

```python
from ddf.domain.models import Entity

entity = Entity()
print(entity.id)       # UUIDv7
print(entity.created_at)  # время в UTC
```

Не создавайте `Entity` напрямую в прикладном коде: обычно от него наследуется модель конкретной предметной области.
