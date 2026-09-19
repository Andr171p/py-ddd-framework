import asyncio
from types import TracebackType

import asyncpg
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class PostgresOutboxListener:
    def __init__(self, engine: AsyncEngine, *, channel: str) -> None:
        self._engine = engine
        self._channel = channel

        self._connection: AsyncConnection | None = None
        self._driver_connection: asyncpg.Connection | None = None

        self._notification = asyncio.Event()

    # ruff: noqa: ARG002
    async def _on_notification(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        self._notification.set()
    # ruff: noqa: END

    async def __aenter__(self) -> "PostgresOutboxListener":
        connection = await self._engine.connect()

        raw_connection = await connection.get_raw_connection()
        driver_connection = raw_connection.driver_connection

        if not isinstance(driver_connection, asyncpg.Connection):
            raise TypeError("PostgresOutboxListener requires SQLAlchemy asyncpg driver.")

        self._connection = connection
        self._driver_connection = driver_connection

        await self._driver_connection.add_listener(self._channel, self._on_notification)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._driver_connection is not None and not self._driver_connection.is_closed():
            await self._driver_connection.remove_listener(self._channel, self._on_notification)

        if self._connection is not None:
            await self._connection.close()

        self._driver_connection = None
        self._connection = None

    async def wait(self, *, timeout: float) -> bool:
        if self._driver_connection is None or self._driver_connection.is_closed():
            raise ConnectionError("PostgreSQL listener connection is closed.")

        try:
            await asyncio.wait_for(self._notification.wait(), timeout=timeout)
        except TimeoutError:
            return False

        self._notification.clear()
        return True
