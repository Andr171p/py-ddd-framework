import pytest

from tests.helpers.dsl.parsing import parse_expression


@pytest.fixture
def parse():
    return parse_expression
