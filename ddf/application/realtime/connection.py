"""
Инфраструктурная обёртка, которая изолирует сетевой ввод-вывод от бизнес-логики.
Реализует паттерн Backpressure через внутреннюю ограниченную очередь задач: защищает
память сервера (OOM) от переполнения, если клиент скачивает данные медленнее,
чем сервер их генерирует.
"""

import asyncio
import logging
import uuid
from enum import Enum, auto

from fastapi import WebSocket, status

from .exceptions import ConnectionClosedError, SlowConsumerError

logger = logging.getLogger(__name__)


class OverflowPolicy(Enum):
    DISCONNECT = auto()
    DROP_OLDEST = auto()
    BLOCK = auto()


class Connection:
    __slots__ = ("_close_code", "_closed", "_dropped", "_overflow", "_queue", "_stopping", "id", "websocket")

    def __init__(
        self,
        websocket: WebSocket,
        *,
        overflow: OverflowPolicy = OverflowPolicy.DISCONNECT,
        queue_size: int = 128,
    ) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")

        self.id = uuid.uuid4()
        self.websocket = websocket

        self._stopping = asyncio.Event()
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)

        self._close_code = status.WS_1001_GOING_AWAY
        self._closed = False
        self._overflow = overflow
        self._dropped = 0

    @property
    def closed(self) -> bool:
        return self._closed or self._stopping.is_set()

    @property
    def close_code(self) -> int:
        return self._close_code

    @property
    def dropped(self) -> int:
        return self._dropped

    def offer(self, message: str) -> bool:
        """Неблокирующая отправка с политикой переполнения."""

        if self.closed:
            return False

        if self._overflow == OverflowPolicy.BLOCK:
            raise RuntimeError("Cannot use sync 'offer()' with OverflowPolicy.BLOCK. Use 'put()'.")

        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            if self._overflow == OverflowPolicy.DISCONNECT:
                self.request_close(status.WS_1013_TRY_AGAIN_LATER)
                return False

            # DROP_OLDEST: удаление старого сообщения
            self._queue.get_nowait()
            self._queue.task_done()
            self._dropped += 1

            self._queue.put_nowait(message)

        return True

    async def put(self, message: str, *, timeout: float = 2.0) -> None:
        """Ожидает свободного места в очереди (backpressure для BLOCK стратегии)."""

        if timeout <= 0:
            raise ValueError("timeout must be positive")

        if self.closed:
            raise ConnectionClosedError()

        if self._overflow != OverflowPolicy.BLOCK:
            logger.warning(
                "Method 'put()' called on connection %s, but active OverflowPolicy is %s. "
                "Falling back to non-blocking 'offer()'. "
                "Use OverflowPolicy.BLOCK for true backpressure blocking.",
                self.id,
                self._overflow.name,
            )
            self.offer(message)
            return

        try:
            async with asyncio.timeout(timeout):
                await self._queue.put(message)

        except asyncio.QueueShutDown as exc:
            raise ConnectionClosedError() from exc

        except TimeoutError as exc:
            self.request_close(status.WS_1013_TRY_AGAIN_LATER)
            raise SlowConsumerError() from exc

    def request_close(self, code: int = status.WS_1001_GOING_AWAY) -> None:
        if self._stopping.is_set():
            return

        self._close_code = code
        self._stopping.set()
        self._queue.shutdown(immediate=True)

    def mark_closed(self) -> None:
        self._closed = True
        self.request_close()

    async def wait_close(self) -> int:
        await self._stopping.wait()
        return self._close_code

    async def write(
        self,
        *,
        send_timeout: float = 15.0,
    ) -> None:
        """Воркер для отправки сообщений в канал (пробрасывает исключение наверх владельцу lifecycle)."""

        if send_timeout <= 0:
            raise ValueError("'send_timeout' must be positive")

        try:
            while True:
                message = await self._queue.get()

                try:
                    async with asyncio.timeout(send_timeout):
                        await self.websocket.send_text(message)
                finally:
                    self._queue.task_done()

        except asyncio.QueueShutDown:
            return
