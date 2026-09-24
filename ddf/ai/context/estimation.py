import inspect
from collections.abc import Awaitable, Callable, Sequence

from .models import ContextItem, ContextUsage

type ContextEstimator[T] = Callable[[Sequence[ContextItem[T]]], int | Awaitable[int]]


async def estimate_context[T](estimator: ContextEstimator, items: Sequence[ContextItem[T]]) -> ContextUsage:
    result = estimator(items)

    if inspect.isawaitable(result):
        result = await result

    return ContextUsage(input_tokens=result)


__all__ = ["ContextEstimator", "estimate_context"]
