import asyncio
from collections.abc import Callable
from datetime import timedelta

from ddf.application.events import EventPublisher, deserialize_event
from ddf.application.uow import UnitOfWork

from .config import OutboxConfig
from .message import OutboxMessage
from .outbox_store import OutboxStore

type RetryPolicy = Callable[[int], timedelta]


def exponential_retry_policy(attempt: int) -> timedelta:
    """
    Вычисляет экспоненциальную задержку перед следующей попыткой отправки.

    Формула: base * 2 ** (attempt - 1), где начальная задержка составляет 5 секунд,
    а максимальное время ожидания ограничено 300 секундами (5 минут).

    Пример значений:
        - Попытка 1: 5 сек
        - Попытка 2: 10 сек
        - Попытка 3: 20 сек
        - ...
        - Попытка 7+: 300 сек
    """

    return timedelta(seconds=min(5 * 2 ** (attempt - 1), 300))


class OutboxProcessor:
    def __init__(
            self,
            uow: UnitOfWork,
            outbox_store: OutboxStore,
            publisher: EventPublisher,
            *,
            config: OutboxConfig,
            retry_policy: RetryPolicy = exponential_retry_policy,
    ) -> None:
        self._uow = uow
        self._outbox_store = outbox_store
        self._publisher = publisher
        self._config = config
        self._retry_policy = retry_policy

    async def process(self) -> int:
        messages = await self._outbox_store.acquire(limit=self._config.batch_size)

        if not messages:
            await self._uow.commit()
            return 0

        async def _publish_one(message: OutboxMessage) -> None:
            try:
                event = deserialize_event(message.type, message.payload)
                await self._publisher([event])
                message.mark_processed()
            except Exception as exc:
                retry_after = self._retry_policy(message.attempts + 1)
                message.mark_failed(
                    str(exc),
                    retry_after=retry_after,
                    max_attempts=self._config.max_attempts,
                )

        semaphore = (
            asyncio.Semaphore(self._config.max_concurrency)
            if self._config.concurrency_enable
            else None
        )

        async def _process_one(message: OutboxMessage) -> None:
            """Публикует одно outbox-сообщение и обновляет его состояние."""

            if semaphore:
                async with semaphore:
                    await _publish_one(message)
            else:
                await _publish_one(message)

        if self._config.concurrency_enable:
            tasks = [_process_one(message) for message in messages]
            await asyncio.gather(*tasks)

        else:
            for message in messages:
                await _process_one(message)

        await self._outbox_store.save_all(messages)
        await self._uow.commit()

        return len(messages)
