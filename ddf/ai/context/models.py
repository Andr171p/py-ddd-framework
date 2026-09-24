from typing import Annotated, Any

from collections.abc import Mapping
from dataclasses import dataclass, field

from typing_extensions import Doc


@dataclass(frozen=True, slots=True)
class ContextItem[T]:
    """"""

    value: T
    priority: Annotated[int, Doc("Чем больше значение, тем важнее элемент")]
    pinned: Annotated[bool, Doc("Запрещает удаление элемента при сокращении контекста")] = False
    group_id: Annotated[str | None, Doc("Идентификатор атомарной группы элементов")] = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContextUsage:
    """Оценка размера контекста модели."""

    input_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError("inputTokens must be >= 0")


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Максимальный доступный размер входного контекста."""

    max_input_tokens: int

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0:
            raise ValueError("maxInputTokens must be > 0")

    def fits(self, usage: ContextUsage) -> bool:
        return usage.input_tokens <= self.max_input_tokens


@dataclass(frozen=True, slots=True)
class ContextReduction:
    """Результат одного шага сокращения."""

    reducer: str

    before: ContextUsage
    after: ContextUsage

    items_before: int
    items_after: int


@dataclass(frozen=True, slots=True)
class ManagedContext[T]:
    """Результат подготовки контекста."""

    items: tuple[ContextItem[T], ...]
    usage: ContextUsage

    reductions: tuple[ContextReduction, ...] = ()

    @property
    def values(self) -> tuple[T, ...]:
        return tuple(item.value for item in self.items)
