from collections.abc import Sequence

from .estimation import ContextEstimator, estimate_context
from .exceptions import ContextBudgetExceededError, InvalidContextReductionError
from .models import ContextBudget, ContextItem, ContextReduction, ManagedContext
from .reduction import ContextReducer
from .validation import validate_reduction


class ContextManager[T]:
    def __init__(self, estimator: ContextEstimator[T], reducers: Sequence[ContextReducer[T]]) -> None:
        self._estimator = estimator
        self._reducers = tuple(reducers)

    async def fit(self, items: Sequence[ContextItem[T]], *, budget: ContextBudget):
        current = tuple(items)
        usage = await estimate_context(self._estimator, current)

        if budget.fits(usage):
            return ManagedContext(items=current, usage=usage)

        reductions: list[ContextReduction] = []

        for reducer in self._reducers:
            candidate = await reducer.reduce(
                items=current,
                usage=usage,
                budget=budget,
                estimator=self._estimator,
            )

            if candidate is None:
                continue

            validate_reduction(before=current, after=candidate, reducer=reducer.name)

            candidate_usage = await estimate_context(self._estimator, candidate)
            if candidate_usage.input_tokens >= usage.input_tokens:
                msg = (
                    f"Reducer {reducer.name!r} did not reduce context: "
                    f"{usage.input_tokens} -> "
                    f"{candidate_usage.input_tokens} tokens"
                )
                raise InvalidContextReductionError(msg)

            reductions.append(
                ContextReduction(
                    reducer=reducer.name,
                    before=usage,
                    after=candidate_usage,
                    items_before=len(current),
                    items_after=len(candidate),
                )
            )

            current = candidate
            usage = candidate_usage

            if budget.fits(usage):
                return ManagedContext(items=current, usage=usage, reductions=tuple(reductions))

        raise ContextBudgetExceededError(
            input_tokens=usage.input_tokens,
            max_input_tokens=budget.max_input_tokens,
        )
