import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, WebSocketException, status
from starlette.websockets import WebSocketState

from ddf.application.realtime import Connection, ConnectionManager, Room

from .config import WsConfig

logger = logging.getLogger(__name__)

type ConnectionHandler = Callable[[Connection], Awaitable[None]]


async def _receive(connection: Connection, handler: ConnectionHandler) -> None:
    """Запускает обработчик соединения, нормализует ожидаемый disconnect."""
    with contextlib.suppress(WebSocketDisconnect, OSError):
        await handler(connection)


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


async def _run(connection: Connection, handler: ConnectionHandler, config: WsConfig) -> int | None:
    tasks = (
        asyncio.create_task(_receive(connection, handler), name=f"ws-recv:{connection.id}"),
        asyncio.create_task(_send(connection, config.send_timeout), name=f"ws-send:{connection.id}"),
        asyncio.create_task(connection.wait_close(), name=f"ws-close:{connection.id}"),
    )

    receiver, sender, closing = tasks

    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Исключения име.т приоритет наж штатными завершениями
        for task in done:
            if not task.cancelled() and (error := task.exception()):
                raise error

        if receiver in done and not receiver.cancelled():
            return None

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
    config: WsConfig,
    manager: ConnectionManager,
    handler: ConnectionHandler,
    *,
    initial_rooms: Iterable[Room] = (),
) -> None:
    """Обслуживает одно аутентифицированное WebSocket-соединение."""

    if manager.closing:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    await websocket.accept()

    close_code: int | None = status.WS_1001_GOING_AWAY
    close_reason = ""

    try:
        if manager.closing:
            close_code = status.WS_1013_TRY_AGAIN_LATER
            return

        connection = Connection(websocket, queue_size=config.queue_size, overflow=config.overflow)

        with manager.connect(connection):
            for room in initial_rooms:
                manager.join(connection, room)

            close_code = await _run(connection, handler, config)
    except WebSocketException as exc:
        close_code = exc.code
        close_reason = exc.reason or ""
    except Exception:
        close_code = status.WS_1011_INTERNAL_ERROR
        logger.exception("WebSocket session failed")
        raise
    finally:
        await _close(websocket, close_code, close_reason, config.close_timeout)


__all__ = ["serve_websocket"]
