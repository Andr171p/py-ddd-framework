from decimal import Decimal

from .catalog.models import ModelPricing


def estimate_cost(
    pricing: ModelPricing,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
) -> Decimal:
    """Рассчитывает стоимость запроса к модели на основе её ценообразования."""

    unit = 1_000_000

    cached = min(cached_input_tokens, input_tokens)
    regular = input_tokens - cached

    input_cost = Decimal(regular) * pricing.input_per_million / unit

    if cached and pricing.cached_input_per_million is not None:
        input_cost += Decimal(cached) * pricing.cached_input_per_million / unit

    else:
        input_cost += Decimal(cached) * pricing.input_per_million / unit

    output_cost = Decimal(output_tokens) * pricing.output_per_million / unit

    return input_cost + output_cost
