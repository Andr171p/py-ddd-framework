import asyncio
import os
import time
from collections.abc import AsyncIterator, Iterator

import pytest
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ddf.application.dsl import Condition, Expression, Group, Negation, Search
from ddf.application.dtos import OffsetPagination, Page, Sort
from tests.helpers.dsl.dataset import Ticket, load_tickets
from tests.helpers.dsl.mongo_catalog import TicketRepository as MongoTicketRepository
from tests.helpers.dsl.mongo_catalog import documents
from tests.helpers.dsl.paging import RESULT_PAGE_SIZE
from tests.helpers.dsl.parsing import parse_expression
from tests.helpers.dsl.sql_catalog import TicketRepository as SqlTicketRepository
from tests.helpers.dsl.sql_catalog import create_schema, replace_rows

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

SERVER_SELECTION_TIMEOUT_MS = 5000
POSTGRES_IMAGE = "postgres:16-alpine"
MONGO_IMAGE = "mongo:8"


class QueryEngine:
    async def codes(self, payload: object) -> set[str]:
        page = await self.page(payload, page=1, size=RESULT_PAGE_SIZE, sort=None)
        return {item.code for item in page.items}

    async def page(self, payload: object, *, page: int, size: int, sort: Sort | None) -> Page[Ticket]:
        raise NotImplementedError


class SqlQuery(QueryEngine):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def page(self, payload: object, *, page: int, size: int, sort: Sort | None) -> Page[Ticket]:
        async with self._sessions() as session:
            repository = SqlTicketRepository(session)
            return await repository.find(
                OffsetPagination(page=page, size=size),
                _expression(payload),
                sort,
            )


class MongoQuery(QueryEngine):
    def __init__(self, repository: MongoTicketRepository) -> None:
        self._repository = repository

    async def page(self, payload: object, *, page: int, size: int, sort: Sort | None) -> Page[Ticket]:
        return await self._repository.find(
            OffsetPagination(page=page, size=size),
            _expression(payload),
            sort,
        )


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
        username="dsl",
        password="dsl",
        dbname="dsl",
    ) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def mongo_url() -> Iterator[str]:
    from testcontainers.community.mongodb import MongoDbContainer

    with MongoDbContainer(MONGO_IMAGE, username="dsl", password="dsl") as mongo:
        url = mongo.get_connection_url()
        separator = "&" if "?" in url else "?"
        yield f"{url}{separator}authSource=admin"


@pytest.fixture
async def postgres(postgres_url: str) -> AsyncIterator[SqlQuery]:
    if len(load_tickets()) > RESULT_PAGE_SIZE:
        raise AssertionError("The result page cannot hold the fixture.")

    engine = create_async_engine(postgres_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await create_schema(engine)
    async with sessions() as session:
        await replace_rows(session)

    try:
        yield SqlQuery(sessions)
    finally:
        await engine.dispose()


@pytest.fixture
async def mongo(mongo_url: str) -> AsyncIterator[MongoQuery]:
    client: AsyncMongoClient = AsyncMongoClient(
        mongo_url,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        directConnection=True,
    )
    await _wait_until_mongo_accepts(client)
    collection = client["dsl"]["tickets"]
    await collection.delete_many({})
    await collection.insert_many(documents())

    try:
        yield MongoQuery(MongoTicketRepository(collection))
    finally:
        await client.close()


async def _wait_until_mongo_accepts(client: AsyncMongoClient) -> None:
    deadline = time.monotonic() + 20
    while True:
        try:
            await client.admin.command("ping")
            return
        except PyMongoError:
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.3)


def _expression(payload: object) -> Expression:
    if isinstance(payload, Condition | Group | Negation | Search):
        return payload
    return parse_expression(payload)
