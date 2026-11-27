"""PostgreSQL fixtures for optimistic locking integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ddf.infra.outbox.sqlalchemy.models import OutboxMessageOrm
from tests.helpers.sqlalchemy.versioned_catalog import WidgetRow, create_schema

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

POSTGRES_IMAGE = "postgres:16-alpine"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    root = os.path.dirname(__file__)
    for item in items:
        if str(item.path).startswith(root):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(
        POSTGRES_IMAGE,
        driver="asyncpg",
        username="ol",
        password="ol",
        dbname="ol",
    ) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
async def session_factory(postgres_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(postgres_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await create_schema(engine, with_outbox=True)

    try:
        yield sessions
    finally:
        await engine.dispose()


@pytest.fixture
async def clean_tables(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    async with session_factory() as session:
        await session.execute(delete(OutboxMessageOrm))
        await session.execute(delete(WidgetRow))
        await session.commit()

    yield

    async with session_factory() as session:
        await session.execute(delete(OutboxMessageOrm))
        await session.execute(delete(WidgetRow))
        await session.commit()
