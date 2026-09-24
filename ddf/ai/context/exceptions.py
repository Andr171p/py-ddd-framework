from dataclasses import dataclass


@dataclass
class ContextBudgetExceededError(Exception):
    """Не удалось сократить контекст до требуемого размера."""

    input_tokens: int
    max_input_tokens: int

    def __post_init__(self) -> None:
        msg = f"Context exceeds the available budget: {self.input_tokens} > {self.max_input_tokens} tokens"
        super().__init__(msg)


class InvalidContextReductionError(Exception):
    """Стратегия сжатия контекста нарушила инварианты context management."""
