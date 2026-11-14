import os

import pytest

from tests.e2e.harness import WS_A, WS_B, ensure_instances, stack_down, stack_up


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "destructive: останавливает/убивает инстансы; требует восстановления стенда",
    )


@pytest.fixture(scope="session")
def e2e_stack():
    managed = os.getenv("E2E_MANAGE_COMPOSE", "1") == "1"
    if managed:
        stack_up()

    try:
        yield {"a": WS_A, "b": WS_B}
    finally:
        if managed and os.getenv("E2E_KEEP_COMPOSE", "0") != "1":
            stack_down()


@pytest.fixture(autouse=True)
def _restore_after_destructive(request: pytest.FixtureRequest, e2e_stack):
    """Только destructive-тесты трогают стенд; остальные не ждут readiness зря."""

    yield
    if request.node.get_closest_marker("destructive"):
        ensure_instances(recreate=("ws-a", "ws-b"))


@pytest.fixture
def url_a(e2e_stack) -> str:
    return e2e_stack["a"]


@pytest.fixture
def url_b(e2e_stack) -> str:
    return e2e_stack["b"]
