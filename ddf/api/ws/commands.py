import asyncio
from uuid import UUID

from fastapi import WebSocketException, status
from pydantic import TypeAdapter, ValidationError

from ddf.application.realtime import (
    Connection,
    ConnectionManager,
    ErrorPayload,
    Reply,
    RoomResolver,
    Subscribe,
    SubscriptionCommand,
)
from ddf.application.realtime.exceptions import SubscriptionDeniedError, TooManySubscriptionsError

from .config import WsConfig
from .dependencies import get_ws_container

_command_adapter: TypeAdapter[SubscriptionCommand] = TypeAdapter(SubscriptionCommand)


def send_reply(connection: Connection, type: str, payload: object, reply_to: UUID | None = None) -> None:
    """Добавляет ответ в исходящую очередь соединения."""

    reply = Reply(type=type, reply_to=reply_to, payload=payload)
    connection.offer(reply.model_dump_json(by_alias=True, exclude_none=True))


async def dispatch_subscription_command(
    command: SubscriptionCommand,
    *,
    connection: Connection,
    connection_manager: ConnectionManager,
    resolve_room: RoomResolver | None,
    timeout: float,
) -> None:
    """Выполняет одну проверенную команду подписки."""

    if not isinstance(command, Subscribe):
        connection_manager.unsubscribe(connection, command.payload)
        send_reply(connection, "subscription.unsubscribed", command.payload, command.id)
        return

    if resolve_room is None:
        error_payload = ErrorPayload(code="not_supported", message="Subscriptions are disabled")
        send_reply(connection, "error", error_payload, command.id)
        return

    try:
        async with asyncio.timeout(timeout):
            room = await resolve_room(command.payload)
    except SubscriptionDeniedError:
        connection_manager.unsubscribe(connection, command.payload)
        error_payload = ErrorPayload(code="forbidden", message="Subscription denied")
        send_reply(connection, "error", error_payload, command.id)
        return
    except TimeoutError:
        connection_manager.unsubscribe(connection, command.payload)
        error_payload = ErrorPayload(code="authorization_timeout", message="Authorization timed out")
        send_reply(connection, "error", error_payload, command.id)
        return

    try:
        connection_manager.subscribe(connection, command.payload, room)

    except TooManySubscriptionsError:
        error_payload = ErrorPayload(code="subscription_limit", message="Subscription limit exceeded")
        send_reply(connection, "error", error_payload, command.id)
        return

    send_reply(connection, "subscription.subscribed", command.payload, command.id)


async def handle_subscription_commands(connection: Connection, *, resolve_room: RoomResolver) -> None:
    """Принимает и обрабатывает команды подписки вплоть до отключения."""

    container = get_ws_container(connection.websocket)
    config, connection_manager = container.config, container.connection_manager

    invalid = 0

    while True:
        message = await connection.websocket.receive()

        if message["type"] == "websocket.disconnect":
            return

        if message["type"] != "websocket.receive":
            raise WebSocketException(code=status.WS_1002_PROTOCOL_ERROR)

        raw = message.get("text")
        validated = _validate_raw_text(config, raw)

        try:
            command = _command_adapter.validate_json(validated)
        except ValidationError:
            invalid += 1

            if invalid >= config.subscription.max_consecutive_invalid_commands:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Too many invalid commands",
                ) from None

            error_payload = ErrorPayload(code="invalid_command", message="Invalid command")
            send_reply(connection, "error", error_payload)
            continue

        invalid = 0
        await dispatch_subscription_command(
            command,
            connection=connection,
            connection_manager=connection_manager,
            resolve_room=resolve_room,
            timeout=config.subscription.authorization_timeout,
        )


def _validate_raw_text(config: WsConfig, raw: object) -> str:
    if not isinstance(raw, str):
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)

    if len(raw.encode("utf-8")) > config.max_incoming_bytes:
        raise WebSocketException(code=status.WS_1009_MESSAGE_TOO_BIG)

    return raw


__all__ = ["dispatch_subscription_command", "handle_subscription_commands", "send_reply"]
