from collections.abc import Sequence

from ddf.ai.catalog import ModelSpec
from ddf.ai.routing.models import ModelRoutingRequest


def smallest_context(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
    """Выбирает подходящую модель с наименьшим контекстным окном."""

    return min(candidates, key=lambda model: model.context_window, default=None)
