from typing import Annotated

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status

from ddf.ratelimit.base import RateLimiter
from ddf.ratelimit.models import RateLimitPolicy

from .common import build_rate_limit_key, get_rate_limiter, rejection_headers, validate_rule


def rate_limit(
    name: str,
    policy: RateLimitPolicy,
    *,
    identity: Callable[..., str],
    cost: int = 1,
) -> Callable[..., Awaitable[None]]:
    validate_rule(name, cost)

    async def dependency(
        subject: Annotated[str, Depends(identity)],
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        result = await limiter.acquire(key=build_rate_limit_key(name, subject), policy=policy, cost=cost)

        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers=rejection_headers(result),
            )

    return dependency
