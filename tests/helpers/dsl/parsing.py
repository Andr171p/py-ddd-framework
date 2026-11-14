from pydantic import TypeAdapter

from ddf.application.dsl import Expression

ADAPTER: TypeAdapter[Expression] = TypeAdapter(Expression)


def parse_expression(payload: object) -> Expression:
    return ADAPTER.validate_python(payload)
