from typing import Any

from faststream.redis import RedisBroker

from ddf.application.realtime import ConnectionManager
from ddf.infra.realtime.dtos import RealtimeDelivery


def register_redis_realtime_consumer(
    broker: RedisBroker,
    connection_manager: ConnectionManager,
    *,
    channel: str = "ddf.realtime",
) -> None:

    @broker.subscriber(channel)
    async def consume(delivery: RealtimeDelivery[Any]) -> None:
        connection_manager.emit(delivery.event, to=delivery.room)
