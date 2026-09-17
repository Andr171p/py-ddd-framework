import re
from collections.abc import Sequence

from faststream.rabbit import RabbitBroker

from ddf.application.events import EventPublisher, run_in_parallel, run_in_sequence
from ddf.domain.events import Event

from .config import RabbitConfig


def get_rabbit_routing_key(event: Event) -> str:
    """
    Определяет ключ маршрутизации на основе имени доменного события.

    Преобразует CamelCase имя класса в lowercase с разделением точками,
    убирая суффикс 'Event'.

    Примеры преобразования:
        - OrderCreatedEvent -> order.created.v1
        - UserRegistered -> user.registered.v1
        - PaymentProcessedEvent -> payment.processed.v2
        - UserProfileUpdatedEvent -> user.profile.updated.v1
    """

    name = event.__class__.__name__.removesuffix("Event")
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", ".", name).lower()
    return f"{separated}.v{event.version}"


def create_rabbit_publisher(
    broker: RabbitBroker,
    config: RabbitConfig,
    *,
    use_concurrent: bool = False,
    max_concurrent: int | None = None,
) -> EventPublisher:
    """
    Фабрика для сборки EventPublisher под RabbitMQ.

    Args:
        broker: Экземпляр RabbitBroker из FastStream для физической отправки сообщений.
        config: Объект конфигурации RabbitConfig, содержащий настройки exchange.
        use_concurrent: Флаг для переключения режима отправки. Если True — события
            публикуются параллельно через asyncio.gather, если False — строго последовательно.
        max_concurrent: Максимальное количество одновременно выполняемых сетевых запросов
            к брокеру в параллельном режиме (лимит асинхронного семафора). Используется
            только при use_concurrent=True.

    Returns:
        Callable (EventPublisher), готовую к интеграции в Application слой.
    """

    async def publish(event: Event) -> None:
        await broker.publish(event, queue=get_rabbit_routing_key(event), exchange=config.exchange)

    async def rabbit_publisher(events: Sequence[Event]) -> None:
        if not events:
            return

        if use_concurrent:
            await run_in_parallel(events, publish, max_concurrent=max_concurrent)
        else:
            await run_in_sequence(events, publish)

    return rabbit_publisher
