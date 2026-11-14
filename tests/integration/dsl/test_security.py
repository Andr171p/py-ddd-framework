import pytest

from tests.helpers.dsl.cases import require_case
from tests.helpers.dsl.dataset import by_code
from tests.helpers.dsl.expressions import condition

HOSTILE_FIELDS = (
    "internalNote",
    "organizationId",
    "deletedAt",
    "code",
    "__dict__",
    "status.name",
    "assigneeName.id",
    "$where",
    "title; drop table dsl_tickets",
)


@pytest.mark.security
async def test_unknown_fields_are_rejected_before_the_query(postgres, mongo, postgres_url, mongo_url):
    for field in HOSTILE_FIELDS:
        payload = condition(field, "$eq", "x")
        with pytest.raises(ValueError) as postgres_error:
            await postgres.codes(payload)
        with pytest.raises(ValueError) as mongo_error:
            await mongo.codes(payload)

        for text, secret in ((str(postgres_error.value), postgres_url), (str(mongo_error.value), mongo_url)):
            assert "Traceback" not in text
            assert secret not in text

    opened = require_case("status-open")
    assert await postgres.codes(opened.expression) == opened.codes
    assert await mongo.codes(opened.expression) == opened.codes


@pytest.mark.security
async def test_quote_payload_does_not_widen_the_result(postgres, mongo):
    title = by_code("quote").title
    opened = require_case("status-open")

    assert await postgres.codes(condition("title", "$eq", title)) == {"quote"}
    assert await mongo.codes(condition("title", "$eq", title)) == {"quote"}
    assert await postgres.codes(condition("title", "$like", title)) == {"quote"}
    assert await mongo.codes(condition("title", "$like", title)) == {"quote"}
    assert await postgres.codes(condition("status", "$in", ["open", title])) == opened.codes
    assert await mongo.codes(condition("status", "$in", ["open", title])) == opened.codes
