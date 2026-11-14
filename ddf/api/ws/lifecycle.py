import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, WebSocketException, status
from starlette.websockets import WebSocketState

from ddf.application.realtime import Connection, Room

from .config import WsConfig
from .dependencies import WsAdmission, get_ws_container

logger = logging.getLogger(__name__)

type ConnectionHandler = Callable[[Connection], Awaitable[None]]


async def _receive(connection: Connection, handler: ConnectionHandler) -> int | None:
    """Запускает обработчик соединения, нормализует ожидаемый disconnect."""

    try:
        await handler(connection)
    except (WebSocketDisconnect, OSError):
        return None

    if connection.websocket.client_state == WebSocketState.DISCONNECTED:
        return None

    return status.WS_1000_NORMAL_CLOSURE


async def _send(connection: Connection, timeout: float) -> int | None:
    """Превращает завершение writer в соответствующий WebSocket close code."""
    try:
        await connection.write(send_timeout=timeout)
    except (WebSocketDisconnect, OSError):
        return None
    except TimeoutError:
        return status.WS_1013_TRY_AGAIN_LATER

    if connection.closed:
        return connection.close_code

    return status.WS_1011_INTERNAL_ERROR


async def _run(
    connection: Connection,
    handler: ConnectionHandler,
    config: WsConfig,
    admission: WsAdmission,
) -> int | None:
    tasks = (
        asyncio.create_task(_receive(connection, handler), name=f"ws-recv:{connection.id}"),
        asyncio.create_task(_send(connection, config.send_timeout), name=f"ws-send:{connection.id}"),
        asyncio.create_task(connection.wait_close(), name=f"ws-close:{connection.id}"),
        asyncio.create_task(admission.lost.wait(), name=f"ws-lease:{connection.id}"),
    )

    receiver, sender, closing, lease_lost = tasks

    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Исключения имеют приоритет над штатными завершениями
        for task in done:
            if not task.cancelled() and (error := task.exception()):
                raise error

        if lease_lost in done:
            return status.WS_1013_TRY_AGAIN_LATER

        if receiver in done and not receiver.cancelled():
            return receiver.result()

        for task in (closing, sender):
            if task in done and not task.cancelled():
                return task.result()

        return status.WS_1001_GOING_AWAY
    finally:
        connection.request_close()

        for task in tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)


async def _close(websocket: WebSocket, code: int | None, reason: str, timeout: float) -> None:
    """Выполняет ограниченное по времени закрытие транспорта."""

    if code is None:
        return

    if websocket.application_state != WebSocketState.CONNECTED:
        return

    with contextlib.suppress(WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
        async with asyncio.timeout(timeout):
            await websocket.close(code=code, reason=reason)


async def serve_websocket(
    websocket: WebSocket,
    handler: ConnectionHandler,
    *,
    admission: WsAdmission,
    initial_rooms: Iterable[Room] = (),
) -> None:
    """Обслуживает одно аутентифицированное WebSocket-соединение."""

    container = get_ws_container(websocket)
    config, connection_manager = container.config, container.connection_manager

    if connection_manager.closing or admission.lost.is_set():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    close_code: int | None = status.WS_1001_GOING_AWAY
    close_reason = ""

    try:
        await websocket.accept()

        if connection_manager.closing or admission.lost.is_set():
            close_code = status.WS_1013_TRY_AGAIN_LATER
            return

        connection = Connection(websocket, queue_size=config.queue_size, overflow=config.overflow)

        with connection_manager.connect(connection):
            for room in initial_rooms:
                connection_manager.join(connection, room)

            close_code = await _run(connection, handler, config, admission)
    except WebSocketException as exc:
        close_code = exc.code
        close_reason = exc.reason or ""
    except Exception:
        close_code = status.WS_1011_INTERNAL_ERROR
        logger.exception("WebSocket session failed")
        raise
    finally:
        await _close(websocket, close_code, close_reason, config.close_timeout)


__all__ = ["ConnectionHandler", "serve_websocket"]
