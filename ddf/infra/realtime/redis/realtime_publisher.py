from typing import Any

from faststream.redis import RedisBroker

from ddf.application.realtime import Event, RealtimePublisher, Room
from ddf.infra.realtime.dtos import RealtimeDelivery


def create_redis_realtime_publisher(
    broker: RedisBroker,
    *,
    channel: str = "ddf.realtime",
) -> RealtimePublisher:

    async def publish(event: Event[Any], *, to: Room) -> None:
        delivery = RealtimeDelivery[Any](room=to, event=event)
        await broker.publish(delivery.model_dump(mode="json", by_alias=True), channel=channel)

    return publish
