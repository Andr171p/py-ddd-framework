from collections.abc import Callable, Sequence
from enum import StrEnum

from ddf.ai.catalog import ModelSpec
from ddf.ai.routing.models import ModelRoutingRequest
from ddf.ai.routing.types import RoutingStrategy

type ModelScore = Callable[[ModelSpec, ModelRoutingRequest], float | None]


class ScoreOrder(StrEnum):
    MIN = "min"
    MAX = "max"


def by_score(score: ModelScore, *, order: ScoreOrder = ScoreOrder.MAX) -> RoutingStrategy:
    """Выбирает модель с минимальным или максимальным пользовательским score."""

    def strategy(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
        scored = ((model, value) for model in candidates if (value := score(model, request)) is not None)
        selector = min if order is ScoreOrder.MIN else max

        try:
            return selector(scored, key=lambda item: item[1])[0]
        except ValueError:
            return None

    return strategy
