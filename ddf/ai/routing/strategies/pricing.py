from collections.abc import Sequence

from ddf.ai.models import ModelSpec
from ddf.ai.routing.routing_request import ModelRoutingRequest
from ddf.ai.utils import estimate_cost


def cheapest_model(candidates: Sequence[ModelSpec], request: ModelRoutingRequest) -> ModelSpec | None:
    """
    Выбирает самую экономичную модель на основе оценки стоимости токенов.

    Функция фильтрует список кандидатов, оставляя только модели с заполненными
    данными о стоимости (pricing). Затем она рассчитывает общую стоимость для
    каждого кандидата на основе предполагаемого количества входных токенов и
    максимального лимита выходных токенов, после чего возвращает самую дешевую модель.
    """

    if request.estimated_input_tokens is None:
        return None

    priced = [model for model in candidates if model.pricing is not None]

    if not priced:
        return None

    output_tokens = request.max_output_tokens or 0
    return min(
        priced,
        key=lambda model: estimate_cost(
            model.pricing,
            input_tokens=request.estimated_input_tokens,
            output_tokens=output_tokens,
        ),
    )
