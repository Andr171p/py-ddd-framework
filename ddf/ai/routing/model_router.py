import inspect
from collections.abc import Sequence

from ddf.ai.catalog import ModelSpec

from .exceptions import ModelRoutingError, NoSuitableModelError
from .matching import model_matches
from .models import ModelRoutingRequest
from .types import RoutingStrategy


class ModelRouter:
    def __init__(self, models: Sequence[ModelSpec], *, strategies: Sequence[RoutingStrategy]) -> None:
        self._models = tuple(models)
        self._strategies = strategies

        self._by_id = {model.id: model for model in self._models}

    def get(self, model_id: str) -> ModelSpec | None:
        return self._by_id.get(model_id)

    async def route(self, request: ModelRoutingRequest) -> ModelSpec:
        """
        Выбирает модель для запроса.

        Сначала исключает модели, не удовлетворяющие обязательным требованиям
        запроса, затем последовательно применяет стратегии маршрутизации.
        Первая стратегия, вернувшая модель, завершает выбор.

        Raises:
            NoSuitableModelError:
                Если ни одна модель не удовлетворяет требованиям запроса.
            ModelRoutingError:
                Если подходящие модели найдены, но ни одна стратегия
                не смогла выбрать модель.
        """

        candidates = tuple(model for model in self._models if model_matches(model, request))

        if not candidates:
            raise NoSuitableModelError("No AI model satisfies the routing requirements.")

        if len(candidates) == 1:
            return candidates[0]

        for strategy in self._strategies:
            result = strategy(candidates, request)

            if inspect.isawaitable(result):
                result = await result

            if result is not None:
                return result

        raise ModelRoutingError(
            "No routing strategy selected a model from {len(candidates)} suitable candidates.",
        )
