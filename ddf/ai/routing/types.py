from typing import Any

from collections.abc import Awaitable, Callable, Mapping, Sequence

from ddf.ai.models import ModelSpec

from .routing_request import ModelRoutingRequest

type RoutingStrategy = Callable[
    [Sequence[ModelSpec], ModelRoutingRequest],
    ModelSpec | Awaitable[ModelSpec | None] | None,
]

type TokenEstimator = Callable[[Mapping[str, Any]], int | Awaitable[int | None] | None]


__all__ = ["RoutingStrategy", "TokenEstimator"]
