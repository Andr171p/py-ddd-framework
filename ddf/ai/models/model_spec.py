from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt


class Modality(StrEnum):
    """Тип данных, который модель может принимать или генерировать."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class ModelCapability(StrEnum):
    """Дополнительные возможности модели, не описываемые модальностью."""

    TOOLS = "tools"
    STRUCTURED_OUTPUT = "structured_output"
    REASONING = "reasoning"
    FILE_INPUT = "file_input"


class ModelPricing(BaseModel):
    """Стоимость использования модели в USD за миллион токенов."""

    input_per_million: Decimal = Field(ge=0, description="Стоимость миллиона входных токенов")
    output_per_million: Decimal = Field(ge=0, description="Стоимость миллиона выходных токенов")
    cached_input_per_million: Decimal | None = Field(
        default=None,
        ge=0,
        description="Стоимость миллиона кешированных входных токенов",
    )


class ModelSpec(BaseModel):
    """Декларативное описание доступной AI модели."""

    id: str = Field(
        description=(
            "Стабильный идентификатор модели внутри каталога. "
            "Не обязан совпадать с идентификатором модели у провайдера."
        ),
    )
    model: str = Field(
        description="Идентификатор модели, передаваемый в OpenAI-compatible API",
        examples=["gpt-5.6-sol"],
    )
    provider: str = Field(
        description="Идентификатор провайдера или источника модели",
        examples=["openai", "vllm", "google"],
    )

    input_modalities: frozenset[Modality] = Field(
        description="Модальности, которые модель может принимать на вход",
    )

    output_modalities: frozenset[Modality] = Field(
        description="Модальности, которые модель может генерировать",
    )

    context_window: NonNegativeInt = Field(
        description="Максимальный размер контекстного окна модели в токенах",
    )
    max_output_tokens: PositiveInt | None = Field(
        default=None,
        description="Максимальное количество токенов ответа",
    )

    capabilities: frozenset[ModelCapability] = Field(
        default_factory=frozenset,
        description="Дополнительные возможности модели",
    )

    pricing: ModelPricing | None = Field(default=None, description="Политика ценообразования")
