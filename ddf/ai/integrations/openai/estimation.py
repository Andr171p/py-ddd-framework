from typing import Any, cast

from collections.abc import Sequence

from openai import AsyncOpenAI
from openai.types.responses import ResponseInputItemParam
from openai.types.responses.input_token_count_params import InputTokenCountParams

from ddf.ai.context import ContextItem


class OpenAiInputTokenEstimator:
    """Расчет токенов для Responses API через вызов к OpenAI.

    Использует метод `input_tokens.count`, что гарантирует точный учет
    всех типов входных данных (текст, изображения, файлы, инструменты)
    с учетом актуальных алгоритмов провайдера.
    """

    def __init__(self, client: AsyncOpenAI, *, params: InputTokenCountParams) -> None:
        if "input" in params:
            raise ValueError("'input' is managed by ContextManager and must not be passed in params.")

        self._client = client
        self._params = dict(params)

    async def __call__(self, items: Sequence[ContextItem[ResponseInputItemParam]]) -> int:
        params: dict[str, Any] = {**self._params, "input": [item.value for item in items]}
        response = await self._client.responses.input_tokens.count(**cast(InputTokenCountParams, params))
        return response.input_tokens
