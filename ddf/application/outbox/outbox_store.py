from typing import Protocol

from collections.abc import Sequence

from .message import OutboxMessage


class OutboxStore(Protocol):

    async def save_all(self, messages: Sequence[OutboxMessage]) -> None:
        """Сохраняет outbox сообщения в текущей транзакции."""

    async def acquire(self, *, limit: int) -> tuple[OutboxMessage, ...]:
        """Захватывает доступные для доставки сообщения, блокируя их."""
