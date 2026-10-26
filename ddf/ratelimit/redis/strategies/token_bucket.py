import math

from ddf.ratelimit.models import TokenBucketPolicy

from .registry import ScriptCall, register_strategy


@register_strategy(TokenBucketPolicy)
def prepare_token_bucket(policy: TokenBucketPolicy, cost: int) -> ScriptCall:
    rate = format(policy.rate_per_ms, ".17g")
    ttl_ms = math.ceil(policy.capacity / policy.rate_per_ms) + 1
    return ScriptCall(
        script="token_bucket.lua",
        signature=f"{policy.capacity}:{rate}",
        limit=policy.capacity,
        args=(policy.capacity, rate, cost, ttl_ms),
    )


__all__ = ["prepare_token_bucket"]
