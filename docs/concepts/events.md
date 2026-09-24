# Доменные события

Доменное событие — неизменяемая запись о факте, который уже произошёл: `OrderPlaced`, `UserRegistered`, `InvoicePaid`. Это не команда и не HTTP-уведомление.

## Регистрация события

Наследуйте событие от `Event`, а агрегат — от `AggregateRoot`/`Entity`. В методе, который меняет состояние, зарегистрируйте факт.

```python
from dataclasses import dataclass
from ddf.domain.events import Event
from ddf.domain.models import AggregateRoot


@dataclass(frozen=True)
class InvoicePaid(Event):
    event_type = "billing.invoice-paid"
    invoice_id: str = ""


@dataclass
class Invoice(AggregateRoot):
    paid: bool = False

    def pay(self) -> None:
        self.paid = True
        self.register_event(InvoicePaid(invoice_id=str(self.id)))
```

Каждое событие получает `event_id` (UUIDv7), `occurred_on` в UTC и версию `1`. У каждого конкретного класса обязательно задайте стабильный `event_type`: по нему Event Store и outbox восстанавливают Python-класс события. Переопределите `version`, если меняете публичный контракт события для потребителей.

`collect_events()` возвращает итератор и **извлекает** события из очереди. Это намеренно: повторная публикация должна быть осознанной политикой обработчика, а не побочным эффектом второй итерации.

## Что делает EventDispatcher

1. Собирает события из переданных сущностей.
2. Если подключён `EventStore`, сохраняет их.
3. Вызывает `uow.commit()`; при ошибке — `uow.rollback()`.
4. После успешного commit передаёт пачку `EventPublisher`.

```python
await repository.update(invoice)
await dispatcher(invoice)
```

Так брокер не получает событие о данных, которые не сохранились. Адаптер RabbitMQ строит routing key из имени: `OrderCreatedEvent` становится `order.created.v1`.

## Доставка: важное ограничение

Порядок «commit, затем publish» не даёт атомарности между базой и брокером. Если процесс упадёт после commit, но до публикации, событие не уйдёт. `EventStore` предоставляет точку расширения, но сам по себе не реализует фоновую доставку.

Для критичных интеграций используйте **transactional outbox**: запишите сообщение в таблицу в той же транзакции, а отдельный worker отправит и отметит его. Это at-least-once доставка, поэтому потребитель должен быть идемпотентен по стабильному ключу сообщения. Полная схема и текущее ограничение адаптера описаны в [разделе про Outbox](../features/outbox.md).

!!! note "Событие — прошлое время"

    Хорошее имя отвечает «что произошло?» (`PaymentCaptured`), а не «что сделать?» (`CapturePayment`). Команда может быть отклонена, событие — уже свершившийся факт.

Причина выбранного порядка описана в [ADR 0004](../decisions/0004-events-after-commit.md).
