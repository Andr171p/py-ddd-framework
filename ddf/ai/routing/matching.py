from ddf.ai.catalog import ModelSpec

from .models import ModelRoutingRequest


def model_matches(model: ModelSpec, request: ModelRoutingRequest) -> bool:
    """
    Проверяет, соответствует ли модель техническим требованиям запроса.

    Проверка выполняется по модальностям (вход/выход), ключевым возможностям,
    лимиту генерируемых токенов и размеру контекстного окна,
    в которое должен вместиться весь суммарный объем токенов.
    """

    if not request.input_modalities <= model.input_modalities:
        return False

    if not request.output_modalities <= model.output_modalities:
        return False

    if not request.required_capabilities <= model.capabilities:
        return False

    if (
        request.max_output_tokens is not None
        and model.max_output_tokens is not None
        and request.max_output_tokens > model.max_output_tokens
    ):
        return False

    if request.estimated_input_tokens is not None:
        required_context = request.estimated_input_tokens

        if request.max_output_tokens is not None:
            required_context += request.max_output_tokens

        if required_context > model.context_window:
            return False

    return True
