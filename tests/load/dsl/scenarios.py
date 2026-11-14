import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.dsl.cases import load_shared_cases  # noqa: E402
from tests.helpers.dsl.expressions import group  # noqa: E402

NEAR_LIMIT_WIDTH = 40
OVERSIZED_VALUE_LENGTH = 64_000

SHARED = load_shared_cases()
INVALID: tuple[dict[str, object], ...] = (
    {"field": "status"},
    {"field": "internalNote", "op": "$eq", "value": "x"},
    {"field": "status", "op": "$nope", "value": "open"},
    {"op": "$and", "filters": []},
    {"field": "status", "filters": []},
)
NEAR_LIMIT = group(
    "$or",
    *({"field": "status", "op": "$eq", "value": "open"} for _ in range(NEAR_LIMIT_WIDTH)),
)
OVERSIZED = {"field": "title", "op": "$eq", "value": "x" * OVERSIZED_VALUE_LENGTH}


def typical_expression() -> dict[str, object]:
    return random.choice(SHARED).expression


def invalid_expression() -> dict[str, object]:
    return random.choice(INVALID)
