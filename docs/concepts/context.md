# Контекст выполнения

`ddf.application.context` переносит небольшой словарь значений по асинхронной цепочке вызовов через `ContextVar`. Он нужен для сквозных технических данных: correlation ID, источника команды, tenant или actor. Контекст не заменяет явные параметры use case и не является хранилищем бизнес-состояния.

## Когда это полезно

- Один `correlation_id` нужен логам, Event Store и исходящим сообщениям.
- Аудиту требуется знать actor или источник операции, но передавать их через десятки инфраструктурных методов не хочется.
- Обработчик HTTP, CLI и consumer брокера должны оставить одинаковый след в telemetry.

## Базовый сценарий

Создайте контекст на границе выполнения — middleware, consumer или CLI-команде. Он автоматически сбрасывается по выходе из блока, даже при исключении.

```python
from uuid import uuid7

from ddf.application.context import extend_context, get_context_value, use_context


async def handle_request(command: CreateInvoice) -> None:
    with use_context({"correlation_id": uuid7(), "source": "http"}):
        await create_invoice(command)


async def create_invoice(command: CreateInvoice) -> None:
    with extend_context({"actor_id": command.actor_id}):
        assert get_context_value("source") == "http"
        # Event Store добавит correlation_id отдельным полем,
        # остальные значения — в meta.
```

`use_context()` заменяет весь словарь. `extend_context()` наследует текущие значения и перекрывает только переданные ключи. `get_context()` возвращает копию — изменение возвращённого словаря не меняет активный context.

## Правила

- Храните только простые, сериализуемые значения: UUID, строки, числа, небольшие словари.
- Не помещайте туда FastAPI `Request`, `AsyncSession`, клиентов Redis/OpenAI, секреты или большой payload. Их жизненный цикл и область видимости должны быть явны.
- Задайте словарь ключей на уровне приложения (`correlation_id`, `actor_id`, `tenant_id`, `source`) и документируйте их семантику. DDF намеренно не навязывает IAM или multi-tenancy модель.
- Если значение меняет бизнес-решение, передавайте его явно в команду/use case. Context подходит для сквозной технической метаинформации, а не для скрытых входных данных.

!!! note "Асинхронная изоляция"

    `ContextVar` изолирует значения между asyncio-задачами при нормальном создании задач. Для фоновой работы, запускаемой позже или в другом процессе, передайте нужную метаинформацию явно: context не является межпроцессным transport-ом.
