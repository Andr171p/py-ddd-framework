import math

from fastapi import Request

from ddf.ratelimit.base import RateLimiter
from ddf.ratelimit.models import RateLimitResult


def get_rate_limiter(request: Request) -> RateLimiter:
    try:
        return request.app.state.rate_limiter
    except AttributeError:
        raise RuntimeError("RateLimiter is not configured in app.state") from None


def validate_rule(name: str, cost: int) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")

    if type(cost) is not int or cost <= 0:
        raise ValueError("cost must be a positive integer")


def build_rate_limit_key(name: str, identity: str) -> str:
    if not isinstance(identity, str) or not identity:
        raise ValueError("identity must be a non-empty string")

    return f"{name}:{len(identity)}:{identity}"


def rejection_headers(result: RateLimitResult) -> dict[str, str]:
    headers = {"Cache-Control": "no-store"}

    if result.retry_after is not None:
        seconds = max(1, math.ceil(result.retry_after.total_seconds()))
        headers["Retry-After"] = str(seconds)

    return headers
