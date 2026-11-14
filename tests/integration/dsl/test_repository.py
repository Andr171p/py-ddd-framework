import asyncio
import contextlib

from pymongo.errors import PyMongoError
from sqlalchemy.exc import DBAPIError

from ddf.application.dtos import Sort
from tests.helpers.dsl.cases import require_case
from tests.helpers.dsl.dataset import TicketSeed
from tests.helpers.dsl.expressions import condition
from tests.helpers.dsl.paging import SAMPLE_PAGE_SIZE, code_pages, ordered, page_count

CONCURRENCY = 12


def _open(ticket: TicketSeed) -> bool:
    return ticket.status == "open"


async def test_offset_pages_are_stable_and_complete(postgres, mongo):
    await _assert_pages(postgres)
    await _assert_pages(mongo)


async def test_parallel_queries_do_not_cross_results(postgres, mongo):
    opened = require_case("status-open")
    closed = require_case("priority-lt-2")
    open_expression = condition("status", "$eq", "open")
    closed_expression = condition("priority", "$lt", 2)

    async def check(engine, expression, expected):
        assert await engine.codes(expression) == expected

    await asyncio.gather(
        *(check(postgres, open_expression, opened.codes) for _ in range(CONCURRENCY)),
        *(check(postgres, closed_expression, closed.codes) for _ in range(CONCURRENCY)),
        *(check(mongo, open_expression, opened.codes) for _ in range(CONCURRENCY)),
        *(check(mongo, closed_expression, closed.codes) for _ in range(CONCURRENCY)),
    )


async def test_a_failed_query_does_not_block_the_next_one(postgres, mongo):
    opened = require_case("status-open")
    bad = condition("priority", "$gt", "not-a-number")

    with contextlib.suppress(ValueError, TypeError, DBAPIError):
        await postgres.codes(bad)
    with contextlib.suppress(ValueError, TypeError, PyMongoError):
        await mongo.codes(bad)

    assert await postgres.codes(opened.expression) == opened.codes
    assert await mongo.codes(opened.expression) == opened.codes


async def _assert_pages(engine) -> None:
    rows = ordered(_open)
    pages = code_pages(rows, SAMPLE_PAGE_SIZE)
    sort = Sort(field="priority", direction="asc")
    seen: list[str] = []

    for number, expected in enumerate(pages, start=1):
        page = await engine.page(
            condition("status", "$eq", "open"),
            page=number,
            size=SAMPLE_PAGE_SIZE,
            sort=sort,
        )
        codes = tuple(item.code for item in page.items)
        assert codes == expected
        assert page.meta.total == len(rows)
        assert page.meta.page == number
        assert page.meta.size == SAMPLE_PAGE_SIZE
        assert page.meta.pages == page_count(len(rows), SAMPLE_PAGE_SIZE)
        assert page.meta.has_next is (number < len(pages))
        assert page.meta.has_prev is (number > 1)
        seen.extend(codes)

    assert seen == [ticket.code for ticket in rows]
    assert len(seen) == len(set(seen))

    empty = await engine.page(
        condition("status", "$eq", "absent"),
        page=1,
        size=SAMPLE_PAGE_SIZE,
        sort=sort,
    )
    assert empty.items == []
    assert empty.meta.total == 0
    assert empty.meta.has_next is False
