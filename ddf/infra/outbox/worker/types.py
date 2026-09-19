from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from ddf.application.outbox import OutboxProcessor

type OutboxWorker = Callable[[], Awaitable[None]]

type ProcessorFactory = Callable[[], AbstractAsyncContextManager[OutboxProcessor]]

__all__ = ["OutboxWorker", "ProcessorFactory"]
