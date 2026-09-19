from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt
from pydantic.alias_generators import to_camel

from ddf.ai.models import Modality, ModelCapability


class ModelRoutingRequest(BaseModel):
    """Нормализованные требования AI-запроса к модели."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, alias_generator=to_camel)

    input_modalities: frozenset[Modality] = Field(
        description="Модальности, присутствующие во входных данных запроса",
    )
    output_modalities: frozenset[Modality] = Field(
        description="Модальности, которые модель должна уметь генерировать",
    )

    required_capabilities: frozenset[ModelCapability] = Field(
        default_factory=frozenset, description="Возможности модели, обязательные для выполнения запроса",
    )

    estimated_input_tokens: NonNegativeInt | None = Field(
        default=None,
        description="Оценочное количество входных токенов",
    )
    max_output_tokens: NonNegativeInt | None = Field(
        default=None,
        description="Максимальное количество выходных токенов",
    )

    input_text: str | None = Field(
        default=None,
        description="Текст запроса, извлечённый из входных данных",
    )
