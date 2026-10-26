from collections.abc import Callable
from dataclasses import dataclass

from ddf.ratelimit.models import BaseRateLimitPolicy


@dataclass(frozen=True, slots=True)
class ScriptCall:
    script: str
    signature: str
    limit: int
    args: tuple[str | int, ...]


type Strategy = Callable[..., ScriptCall]
type PrepareScriptCallFunc[PolicyT: BaseRateLimitPolicy] = Callable[[PolicyT, int], ScriptCall]

_registry: dict[type[...], Strategy] = {}


def register_strategy[PolicyT](
    policy_type: type[PolicyT],
) -> Callable[PrepareScriptCallFunc[PolicyT], PrepareScriptCallFunc[PolicyT]]:
    """Регистрирует стратегию реализации алгоритма ``RateLimiter``."""

    def decorator(func: PrepareScriptCallFunc[PolicyT]) -> PrepareScriptCallFunc[PolicyT]:
        if policy_type in _registry:
            raise ValueError(f"Strategy already registered: {policy_type.__name__}")

        _registry[policy_type] = func
        return func

    return decorator


def prepare_script_call(policy: BaseRateLimitPolicy, cost: int) -> ScriptCall:
    """Подготавливает параметры для вызова скрипта исходя из переданной политики."""

    if (strategy := _registry.get(type(policy))) is None:
        raise ValueError(f"Unsupported rate limit policy: {type(policy).__name__}")

    return strategy(policy, cost)


__all__ = ["ScriptCall", "prepare_script_call", "register_strategy"]
