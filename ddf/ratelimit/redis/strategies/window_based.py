from ddf.ratelimit.models import FixedWindowPolicy, SlidingWindowPolicy, WindowBasedPolicy

from .registry import ScriptCall, register_strategy


def _prepare_window(policy: WindowBasedPolicy, cost: int, *, script: str) -> ScriptCall:
    return ScriptCall(
        script=script,
        signature=f"{policy.limit}:{policy.window_ms}",
        limit=policy.limit,
        args=(policy.limit, policy.window_ms, cost),
    )


@register_strategy(SlidingWindowPolicy)
def prepare_sliding_window(policy: SlidingWindowPolicy, cost: int) -> ScriptCall:
    return _prepare_window(policy, cost, script="sliding_window.lua")


@register_strategy(FixedWindowPolicy)
def prepare_fixed_window(policy: FixedWindowPolicy, cost: int) -> ScriptCall:
    return _prepare_window(policy, cost, script="fixed_window.lua")


__all__ = ["prepare_fixed_window", "prepare_sliding_window"]
