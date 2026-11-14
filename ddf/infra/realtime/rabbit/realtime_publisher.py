from typing import Any

from faststream.rabbit import RabbitBroker, RabbitExchange

from ddf.application.realtime import Event, RealtimePublisher, Room
from ddf.infra.realtime.dtos import RealtimeDelivery


def create_rabbit_realtime_publisher(
    broker: RabbitBroker,
    *,
    exchange: RabbitExchange,
) -> RealtimePublisher:
    async def publish(event: Event[Any], *, to: Room) -> None:
        delivery = RealtimeDelivery[Any](
            room=to,
            event=event,
        )
        await broker.publish(
            delivery.model_dump(mode="json", by_alias=True),
            exchange=exchange,
            routing_key="",
            mandatory=False,
            persist=False,
        )

    return publish
