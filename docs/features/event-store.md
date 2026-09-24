# Журнал доменных событий

Event Store DDF сохраняет историю бизнес-фактов для аудита и диагностики. Он **не** превращает приложение в event-sourced систему: текущее состояние остаётся в обычных таблицах, агрегаты не восстанавливаются replay-ем событий.

## Для каких задач подходит

- аудит: кто и когда подтвердил платёж или изменил статус;
- техническая трассировка изменений вместе с `correlation_id`;
- расследование инцидентов и экспорт бизнес-истории;
- запись фактов перед последующей собственной аналитической обработкой.

Не используйте его как готовую платформу для aggregate replay, snapshots, глобальных позиций стрима или пересборки проекций: таких API в DDF сейчас нет.

## Как данные сохраняются

`SqlAlchemyEventStore` получает пары `(Event, Entity)` от `EventDispatcher`. Он сохраняет envelope отдельно от custom payload:

| Группа | Поля |
| --- | --- |
| Идентичность события | `event_id`, `event_type`, `version`, `occurred_on`, `recorded_at` |
| Связь с моделью | `entity_id`, `entity_type` |
| Контекст | `correlation_id`, `meta` |
| Бизнес-payload | только поля конкретного класса события |

`correlation_id` из execution context получает отдельную колонку; прочие context-значения записываются в JSONB `meta`. Поэтому tenant, actor и другие прикладные измерения не навязываются схемой фреймворка.

```python
from dataclasses import dataclass

from ddf.domain.events import Event


@dataclass(frozen=True)
class InvoicePaid(Event):
    event_type = "billing.invoice-paid"
    invoice_id: str = ""
    amount: str = ""
```

`event_type` — стабильный строковый контракт, а не имя Python-класса. Не меняйте его при переименовании класса. При несовместимом изменении payload увеличьте `version` и сохраните возможность обработать прежний формат у потребителей.

## Подключение

```python
from ddf.application.events import EventDispatcher
from ddf.infra.events.sqlalchemy import SqlAlchemyEventStore


dispatcher = EventDispatcher(
    uow=session_uow,
    evnt_publisher=publisher,
    event_store=SqlAlchemyEventStore(session),
)
```

В use case сначала измените агрегат и сохраните его репозиторием, затем вызовите dispatcher. Он запишет события в текущую транзакцию, выполнит commit и только после успешного commit вызовет publisher.

## Ограничения текущей версии

- Реализована запись `record_all()`; запросный API истории пока не предоставлен, хотя в Protocol зарезервирован `find`.
- В журнале нет глобального sequence/position. UUIDv7 подходит для идентификации и cursor-порядка, но не для строгого event-stream checkpoint.
- Commit-then-publish не атомарен между БД и брокером. Для критичной межсервисной доставки используйте [Transactional Outbox](outbox.md).

!!! warning "Не пишите в payload технический envelope"

    Не дублируйте `event_id`, `event_type`, `occurred_on` и `version` в полях конкретного события. Для Event Store это уже отдельные, индексируемые данные; дублирование создаёт два источника истины.
