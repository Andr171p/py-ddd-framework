# Рецепт: Transactional Outbox в use case

Записывайте бизнес-изменение и `OutboxMessage` через объекты, работающие на одной `AsyncSession`/Unit of Work. Commit должен быть один — после обеих записей.

```python
from ddf.application.events import get_event_payload
from ddf.application.context import get_context_value
from ddf.application.outbox import OutboxMessage, OutboxStore
from ddf.application.uow import UnitOfWork


async def pay_invoice(
    invoice_id: UUID,
    *,
    invoices: InvoiceRepository,
    outbox: OutboxStore,
    uow: UnitOfWork,
) -> None:
    invoice = await invoices.read(invoice_id)
    if invoice is None:
        raise InvoiceNotFound(invoice_id)

    invoice.pay()
    await invoices.update(invoice)

    events = tuple(invoice.collect_events())
    await outbox.save_all([
        OutboxMessage(
            type=event.event_type,
            occurred_on=event.occurred_on,
            payload=get_event_payload(event),
            meta={"correlation_id": str(get_context_value("correlation_id", ""))},
        )
        for event in events
    ])
    await uow.commit()
```

Данный вариант сознательно **не** вызывает `EventDispatcher`: тот извлечёт события и сразу выполнит commit-then-publish, то есть это другой delivery path. Если нужен одновременно audit Event Store и outbox, запишите обе проекции из сохранённого `events` до единственного commit.

## Worker

Worker создаёт свежие session/UoW, store и processor на каждый batch. Не делите одну `AsyncSession` между бесконечным циклом и параллельными worker-ами.

```python
from contextlib import asynccontextmanager

from ddf.application.outbox import OutboxConfig, OutboxProcessor
from ddf.infra.outbox.sqlalchemy import SqlAlchemyOutboxStore
from ddf.infra.outbox.worker import OutboxWorkerConfig, run_polling_worker


@asynccontextmanager
async def processor_factory():
    async with session_factory() as session:
        yield OutboxProcessor(
            # AsyncSession реализует требуемые commit/rollback/flush.
            # В приложении можно передать собственный UnitOfWork-адаптер.
            uow=session,
            outbox_store=SqlAlchemyOutboxStore(session),
            publisher=integration_publisher,
            config=OutboxConfig(),
        )


await run_polling_worker(processor_factory, OutboxWorkerConfig())
```

`integration_publisher` должен формировать transport-сообщение со стабильным idempotency key. См. ограничение о восстановлении `Event` в [руководстве по Outbox](../features/outbox.md).

!!! warning "Не публикуйте внутри транзакции"

    Не вызывайте broker перед `uow.commit()`: при rollback consumer увидит несуществующее состояние. Не публикуйте и сразу после commit в том же use case, если эта интеграция критична: падение процесса создаст потерю между БД и сетью.
