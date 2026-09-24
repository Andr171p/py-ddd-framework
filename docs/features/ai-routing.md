# AI: маршрутизация моделей

`ddf.ai` — optional capability для приложений, которым нужно выбирать между OpenAI-compatible моделями, не создавая собственный универсальный LLM DSL. Core DDF не зависит от OpenAI SDK; подключайте extra только там, где нужен AI:

```shell
uv sync --extra ai
```

## Когда это полезно

- Несколько моделей/провайдеров с разной стоимостью, скоростью или доступностью.
- Запросы с разными техническими требованиями: изображения, tools, JSON schema, reasoning, размер контекста.
- Предсказуемый fallback без того, чтобы каждый use case вручную выбирал модель.

Если в продукте одна модель и один provider, обычно проще использовать официальный `AsyncOpenAI` напрямую. DDF не пытается заменить OpenAI SDK, agents platform, retrieval или vector database.

## Описание каталога и роутинг

`ModelSpec` — декларативный Pydantic-объект: внутренний `id`, provider, API `model`, input/output modalities, контекст, лимит ответа, capabilities и optional pricing. Политика (`fast`, `cheap`, приоритет) намеренно не лежит в `ModelSpec`: одна и та же модель может быть приоритетной для одного продукта и fallback для другого.

Сначала `ModelRouter` отсеивает модели по обязательным constraints, затем применяет стратегии в заданном порядке. Первая стратегия, вернувшая модель, завершает выбор; `None` означает «не могу решить, пробуй следующую».

```python
from ddf.ai.catalog import Modality, ModelCapability, ModelPricing, ModelSpec
from ddf.ai.routing import ModelRouter
from ddf.ai.routing.strategies import cheapest_model, model_priority

models = [
    ModelSpec(
        id="fast", model="fast-model", provider="provider-a",
        input_modalities={Modality.TEXT}, output_modalities={Modality.TEXT},
        context_window=32_000, max_output_tokens=4_000,
        capabilities={ModelCapability.STRUCTURED_OUTPUT},
        pricing=ModelPricing(input_per_million="0.5", output_per_million="2"),
    ),
    ModelSpec(
        id="smart", model="smart-model", provider="provider-b",
        input_modalities={Modality.TEXT, Modality.IMAGE}, output_modalities={Modality.TEXT},
        context_window=128_000, max_output_tokens=16_000,
        capabilities={ModelCapability.TOOLS, ModelCapability.STRUCTURED_OUTPUT},
    ),
]
router = ModelRouter(models, strategies=[cheapest_model, model_priority("smart", "fast")])
```

Доступны `cheapest_model`, `model_priority`, `provider_priority`, `smallest_context`, generic `by_score` и `semantic`. Semantic scorer может быть синхронным или асинхронным и должен вернуть `None` при низкой уверенности, чтобы сработал deterministic fallback.

## RoutedOpenAI

`RoutedOpenAI` использует composition: он держит несколько настоящих `AsyncOpenAI` clients и предоставляет близкий к SDK вызов `responses.create`. Ответ остаётся native SDK response.

```python
from openai import AsyncOpenAI

from ddf.ai.routing import RoutedOpenAI

ai = RoutedOpenAI(
    router=router,
    clients={
        "provider-a": AsyncOpenAI(api_key="...", base_url="https://a.example/v1"),
        "provider-b": AsyncOpenAI(api_key="...", base_url="https://b.example/v1"),
    },
    default_provider="provider-a",
)

response = await ai.responses.create(
    input="Составь краткое резюме документа.",
    max_output_tokens=500,
)
```

Wrapper анализирует структурированные поля запроса: `instructions`, `input_text`, `input_image`, `input_audio`, `input_file`, `tools`, `reasoning`, structured output и `max_output_tokens`. URL, написанный внутри простого текста, остаётся текстом: DDF не скачивает контент и не угадывает MIME-type. File — capability `FILE_INPUT`, а не отдельная modality.

Явный `model=` сначала ищется как внутренний `ModelSpec.id`; при совпадении подставляется model/provider из каталога. Если ID неизвестен, вызов уходит с исходным `model` в `default_provider` — это осознанный escape hatch для provider-specific моделей.

## Токены, цена и ошибки

Token estimation подключается callback-ом. Без него `estimated_input_tokens=None`, поэтому стратегии цены и context могут отказаться от выбора; добавьте последнюю deterministic strategy. Точная оценка не универсальна для изображений, файлов, tool schemas и разных tokenizer-ов.

`ModelPricing` хранит USD за миллион токенов и используется для маршрутизации/наблюдаемости, но не заменяет биллинг. DDF выбрасывает `NoSuitableModelError` при отсутствии технически подходящей модели и `ModelRoutingError`, если стратегии не приняли решение. Ошибки OpenAI SDK (rate limit, timeout, authentication) остаются исходными.

!!! warning "Наблюдаемость и данные"

    Guardrails, OpenTelemetry-инструментация и content splitters описаны в roadmap, но в текущем пакете ещё не реализованы. Не рассчитывайте на automatic PII-redaction или запись prompt/response; добавляйте их в приложении с явной privacy-политикой.
