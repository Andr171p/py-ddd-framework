from openai import AsyncOpenAI
from openai.types.responses import ResponseInputItemParam
from pydantic import BaseModel, Field, PositiveInt

from ddf.ai.context import (
    ContextBudget,
    ContextEstimator,
    ContextItem,
    ContextUsage,
    select_oldest_reducible_slice,
)


class OpenAiSummarizationOldestConfig(BaseModel):
    keep_last: PositiveInt = Field(
        default=6,
        description="Количество последних элементов диалога, которые гарантированно защищены от суммаризации",
    )
    min_items: PositiveInt = Field(
        default=4,
        description="Минимальное число элементов, которые должны остаться после редукции",
    )
    max_output_tokens: PositiveInt = Field(
        default=1024,
        description="Максимальное число токенов после суммаризации",
    )
    instructions: str = Field(min_length=1, description="Промпт для суммаризации контекста")


class OpenAiSummarizationOldestReducer:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str,
        config: OpenAiSummarizationOldestConfig,
    ) -> None:
        self._client = client
        self._model = model
        self._config = config

    @property
    def name(self) -> str:
        return "openai_summarize_oldest"

    async def reduce(
            self,
            items: tuple[ContextItem[ResponseInputItemParam], ...],
            usage: ContextUsage,
            budget: ContextBudget,
            estimator: ContextEstimator[ResponseInputItemParam],
    ) -> tuple[ContextItem[ResponseInputItemParam], ...] | None:
        selected = select_oldest_reducible_slice(
            items,
            keep_last=self._config.keep_last,
            min_items=self._config.min_items,
        )

        if selected is None:
            return None

        source = items[selected.start:selected.stop]

        response = await self._client.responses.create(
            model=self._model,
            instructions=self._config.instructions,
            input=[
                *(item.value for item in source),
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Summarize the preceding context.",
                        }
                    ],
                },
            ],
            max_output_tokens=self._config.max_output_tokens,
        )

        if not (summary := response.output_text.strip()):
            return None

        summary_item: ResponseInputItemParam = {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": f"<context_summary>\n{summary}\n</context_summary>",
                }
            ],
        }
        priority = max((item.priority for item in source), default=0)
        replacement = ContextItem(
            value=summary_item,
            priority=priority,
            meta={
                "reducer": self.name,
                "synthetic": True,
                "source_items": len(source),
            },
        )

        return *items[:selected.start], replacement, *items[selected.stop:]
