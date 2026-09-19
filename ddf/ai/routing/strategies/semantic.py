import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence

from ddf.ai.models import ModelSpec
from ddf.ai.routing.routing_request import ModelRoutingRequest
from ddf.ai.routing.types import RoutingStrategy

type SemanticScorer = Callable[
    [str, Sequence[ModelSpec]],
    Mapping[str, float] | Awaitable[Mapping[str, float]],
]


def semantic(scorer: SemanticScorer, *, min_score: float = 0.0) -> RoutingStrategy:
    """Выбирает модель по семантической близости к входному запросу."""

    async def strategy(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
        if not request.input_text:
            return None

        scores = scorer(request.input_text, candidates)

        if inspect.isawaitable(scores):
            scores = await scores

        scored = ((model, scores[model.id]) for model in candidates if model.id in scores)

        try:
            model, score = max(scored, key=lambda item: item[1])
        except ValueError:
            return None

        return model if score >= min_score else None

    return strategy
