from typing import Protocol

from .estimation import ContextEstimator
from .models import ContextBudget, ContextItem, ContextUsage


class ContextReducer[T](Protocol):
    """Стратегия для сжатия контекста."""

    @property
    def name(self) -> str: ...

    async def reduce(
        self,
        items: tuple[ContextItem[T], ...],
        usage: ContextUsage,
        budget: ContextBudget,
        estimator: ContextEstimator[T],
    ) -> tuple[ContextItem[T], ...]:
        """
        Выполняет сжатия контекста модели.

        Returns:
             Новый набор элементов или ``None``, если стратегия неприменима.
        """
