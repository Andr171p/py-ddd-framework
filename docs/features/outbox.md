# Transactional Outbox

Transactional outbox решает разрыв между транзакцией БД и публикацией в брокер. Вместо «сначала commit, потом сеть» приложение записывает исходящее сообщение в таблицу в той же транзакции, что и изменение агрегата. Отдельный worker затем читает и публикует сообщения.

```text
use case → агрегат + таблицы приложения + outbox_messages → COMMIT
                                                        ↓
                                           worker → broker → consumer
```

## Что гарантируется

Это **at-least-once delivery**. После отправки в брокер процесс может упасть до отметки `processed_at`, и сообщение будет отправлено повторно. Потребитель обязан быть идемпотентным по стабильному ключу интеграционного сообщения.

Outbox не даёт exactly-once, не заменяет DLQ брокера и не задаёт retry-политику входящего consumer-а.

## Модель и состояния

`OutboxMessage` содержит неизменяемый смысл сообщения (`id`, `type`, `payload`, `meta`, `occurred_on`) и изменяемую доставку (`attempts`, `available_at`, `processed_at`, `failed_at`, `last_error`). Поле `status` вычисляется:

| Условие | Статус |
| --- | --- |
| `processed_at` задан | `processed` |
| `failed_at` задан | `failed` |
| иначе | `pending` |

`SqlAlchemyOutboxStore.save_all()` делает PostgreSQL upsert. При конфликте обновляются только delivery-поля, поэтому payload уже созданного сообщения не перезаписывается.

## Обработка и масштабирование

`OutboxProcessor.process()` обрабатывает ровно один batch: захватывает доступные строки, публикует, меняет состояние, сохраняет его и commit-ит. Бесконечный цикл находится в infrastructure worker, а scheduler/TaskIQ остаётся лишь runner-ом.

SQLAlchemy store использует `FOR UPDATE SKIP LOCKED` и partial index по pending-строкам. Несколько worker-процессов могут безопасно выбирать разные batch без отдельного distributed lock. В текущем простом дизайне блокировка строки удерживается во время publish в брокер; при длинных publish или большой нагрузке понадобится отдельная lease/claim-стратегия.

Polling worker работает в drain mode: если обработал сообщения, сразу запускает следующий batch; засыпает только при пустой очереди. PostgreSQL `LISTEN/NOTIFY` — ускоритель пробуждения, а не доставка: durable source of truth — таблица, поэтому worker всегда использует timeout-пolling fallback.

## Конфигурация

```python
from ddf.application.outbox import OutboxConfig
from ddf.infra.outbox.worker import OutboxWorkerConfig

outbox = OutboxConfig(
    batch_size=100,
    max_attempts=5,
    concurrency_enable=False,
)
worker = OutboxWorkerConfig(poll_interval=1.0, error_interval=5.0)
```

Значения также читаются из переменных с префиксами `OUTBOX_` и `OUTBOX_WORKER_`. Включайте параллельную публикацию только если publisher и порядок сообщений это допускают: порядок внутри batch тогда не гарантирован.

## Важное ограничение текущей связки с Event

Outbox processor восстанавливает `Event` из `type` и **custom payload**. Базовые поля `Event` (`event_id`, `occurred_on`, `version`) не входят в payload, а `EventPublisher` принимает только `Sequence[Event]`. Поэтому опубликованный объект получает новые default `event_id` и `occurred_on`; `OutboxMessage.id` до publisher-а не доходит.

До расширения контракта не используйте `Event.event_id` полученного сообщения как ключ дедупликации и не обещайте потребителям исходный timestamp события. Для production-интеграции передавайте стабильный message ID и envelope в transport-контракте своего publisher-а либо адаптируйте outbox к собственному message schema. Это ограничение документации отражает текущую реализацию, а не целевую семантику.

Практический вариант записи в транзакцию приведён в [рецепте](../recipes/transactional-outbox.md).
