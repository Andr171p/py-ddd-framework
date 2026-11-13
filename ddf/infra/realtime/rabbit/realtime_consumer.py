from typing import Any

from uuid import uuid4

from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

from ddf.application.realtime import ConnectionManager
from ddf.infra.realtime.dtos import RealtimeDelivery


def register_rabbit_realtime_consumer(
    broker: RabbitBroker,
    connection_manager: ConnectionManager,
    *,
    exchange: RabbitExchange,
) -> None:
    queue = RabbitQueue(
        name=f"ddf.realtime.{uuid4().hex}",
        durable=False,
        exclusive=True,
        auto_delete=True,
    )

    @broker.subscriber(queue=queue, exchange=exchange)
    async def consume(delivery: RealtimeDelivery[Any]) -> None:
        connection_manager.emit(delivery.event, to=delivery.room)
