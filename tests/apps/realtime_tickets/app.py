from typing import Annotated, Any

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Query, WebSocket, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from ddf.api.ws import (
    WsAdmission,
    WsConfig,
    WsContainer,
    create_ws_admitter,
    handle_subscription_commands,
    serve_websocket,
)
from ddf.application.realtime import ConnectionManager, Event, RealtimePublisher, Room, Subscription
from ddf.infra.limits.concurrency.redis import RedisConcurrencyLimiter
from ddf.ratelimit.redis import RedisRateLimiter

from .rooms import make_resolver, room_for
from .settings import Settings
from .ws_state import WsContainerMiddleware


class TicketStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    org_id: str = Field(min_length=1, max_length=64)


settings = Settings()
ws_config = WsConfig()

redis = Redis.from_url(settings.redis_url, decode_responses=True)
connection_manager = ConnectionManager(max_subscriptions=settings.max_subscriptions)
rate_limiter = RedisRateLimiter(redis, prefix="ddf:rl")
concurrency_limiter = RedisConcurrencyLimiter(redis, prefix="ddf:concurrency")
container = WsContainer(
    config=ws_config,
    connection_manager=connection_manager,
    rate_limiter=rate_limiter,
    concurrency_limiter=concurrency_limiter,
)

runtime: dict[str, Any] = {
    "settings": settings,
    "ready": False,
    "publisher": None,
    "broker": None,
    "redis": redis,
    "container": container,
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    publisher: RealtimePublisher | None = None
    broker = None

    if settings.realtime_backend == "redis":
        from faststream.redis import RedisBroker

        from ddf.infra.realtime.redis import (
            create_redis_realtime_publisher,
            register_redis_realtime_consumer,
        )

        broker = RedisBroker(settings.redis_url)
        register_redis_realtime_consumer(broker, connection_manager)
        publisher = create_redis_realtime_publisher(broker)
        await broker.start()

    elif settings.realtime_backend == "rabbit":
        from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

        from ddf.infra.realtime.rabbit import (
            create_rabbit_realtime_publisher,
            register_rabbit_realtime_consumer,
        )

        exchange = RabbitExchange("ddf.realtime", type=ExchangeType.FANOUT, durable=False)
        broker = RabbitBroker(settings.rabbit_url)
        register_rabbit_realtime_consumer(broker, connection_manager, exchange=exchange)
        publisher = create_rabbit_realtime_publisher(broker, exchange=exchange)
        await broker.start()

    runtime.update(publisher=publisher, broker=broker, ready=True)

    try:
        yield
    finally:
        runtime["ready"] = False
        connection_manager.shutdown()
        if broker is not None:
            await broker.close()
        await redis.aclose()


app = FastAPI(title=f"realtime-tickets-{settings.instance_name}", lifespan=lifespan)
app.add_middleware(WsContainerMiddleware, container=container)
app.state.runtime = runtime


async def get_subject_key(subject: Annotated[str, Query(min_length=1, max_length=128)]) -> str:
    return subject


admit = create_ws_admitter(get_subject_key)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "instance": settings.instance_name}


@app.get("/ready")
async def ready() -> dict[str, str]:
    if not runtime.get("ready"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="not ready")
    await redis.ping()
    return {"status": "ready", "instance": settings.instance_name, "backend": settings.realtime_backend}


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    admission: Annotated[WsAdmission, Depends(admit)],
    org: Annotated[str, Query(min_length=1, max_length=64)] = "acme",
) -> None:
    resolver = make_resolver(org, deny=settings.denied_ticket_keys)
    await serve_websocket(
        websocket,
        handler=lambda connection: handle_subscription_commands(connection, resolve_room=resolver),
        admission=admission,
    )


@app.post("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, body: TicketStatusUpdate) -> dict[str, Any]:
    publisher: RealtimePublisher | None = runtime.get("publisher")
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="publisher unavailable")

    event = Event(
        type="ticket.updated",
        payload={"ticketId": ticket_id, "status": body.status, "orgId": body.org_id},
        occurred_at=datetime.now(UTC),
    )
    room = room_for(body.org_id, Subscription(topic="ticket", key=ticket_id))
    await publisher(event, to=room)
    return {"eventId": str(event.id), "room": str(room), "instance": settings.instance_name}


@app.post("/realtime/publish")
async def publish_raw(
    room: Annotated[str, Query(min_length=1)],
    event_type: Annotated[str, Query(alias="type", min_length=1)] = "test.event",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = Event(type=event_type, payload=payload or {}, occurred_at=datetime.now(UTC))
    publisher: RealtimePublisher | None = runtime.get("publisher")

    if publisher is None:
        connection_manager.emit(event, to=Room(room))
        return {"eventId": str(event.id), "room": room, "mode": "local"}

    await publisher(event, to=Room(room))
    return {"eventId": str(event.id), "room": room, "mode": "broker"}
