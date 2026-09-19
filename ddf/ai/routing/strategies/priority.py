from collections.abc import Sequence

from ddf.ai.models import ModelSpec
from ddf.ai.routing.routing_request import ModelRoutingRequest
from ddf.ai.routing.types import RoutingStrategy


def model_priority(*model_ids: str) -> RoutingStrategy:
    """Выбирает первую доступную модель согласно заданному приоритету."""

    priority = {model_id: i for i, model_id in enumerate(model_ids)}

    def strategy(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
        return min(
            (model for model in candidates if model.id in priority),
            key=lambda model: priority[model.id],
            default=None,
        )

    return strategy


def provider_priority(*providers: str) -> RoutingStrategy:
    """Выбирает модель согласно заданному приоритету провайдеров."""

    priority = {provider: index for index, provider in enumerate(providers)}

    def strategy(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
        return min(
            (model for model in candidates if model.provider in priority),
            key=lambda model: priority[model.provider],
            default=None,
        )

    return strategy
