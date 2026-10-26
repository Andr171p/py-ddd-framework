from typing import Annotated, Literal

import math
from dataclasses import dataclass
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int | None = None
    retry_after: timedelta | None = None


class BaseRateLimitPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    algorithm: str = Field(description="Название реализуемого алгоритма в snake_case")


class TokenBucketPolicy(BaseRateLimitPolicy):

    algorithm: Literal["token_bucket"] = "token_bucket"

    capacity: int = Field(gt=0)
    refill_rate: float = Field(gt=0, allow_inf_nan=False)

    @property
    def rate_per_ms(self) -> float:
        return self.refill_rate / 1000


class WindowBasedPolicy(BaseRateLimitPolicy):
    """Общая конфигурация для алгоритмов основанных на временном окне."""

    model_config = ConfigDict(frozen=True)

    limit: int = Field(gt=0)
    window: timedelta = Field(gt=timedelta(0))

    @property
    def window_ms(self) -> int:
        return math.ceil(self.window.total_seconds() * 1000)


class SlidingWindowPolicy(WindowBasedPolicy):
    algorithm: Literal["sliding_window"] = "sliding_window"


class FixedWindowPolicy(WindowBasedPolicy):
    algorithm: Literal["fixed_window"] = "fixed_window"


type RateLimitPolicy = Annotated[
    TokenBucketPolicy | SlidingWindowPolicy | FixedWindowPolicy,
    Field(discriminator="algorithm"),
]

__all__ = [
    "BaseRateLimitPolicy",
    "FixedWindowPolicy",
    "RateLimitPolicy",
    "RateLimitResult",
    "SlidingWindowPolicy",
    "TokenBucketPolicy",
    "WindowBasedPolicy",
]
