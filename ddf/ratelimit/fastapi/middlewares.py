"""
## Пример использования

```python
from fastapi import FastAPI, Request


def client_ip(request: Request) -> str:
    if request.client is None:
        raise RuntimeError("Client address is unavailable")

    return request.client.host


app.add_middleware(
    RateLimitMiddleware,
    name="global:ip",
    policy=SlidingWindowPolicy(
        limit=100,
        window=timedelta(minutes=1),
    ),
    identity=client_ip,
    exclude_paths=(
        "/health",
        "/metrics",
    ),
)
```
"""


from collections.abc import Callable, Iterable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ddf.ratelimit.models import RateLimitPolicy

from .common import build_rate_limit_key, get_rate_limiter, rejection_headers, validate_rule


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        name: str,
        policy: RateLimitPolicy,
        identity: Callable[[Request], str],
        cost: int = 1,
        exclude_paths: Iterable[str] = (),
    ) -> None:
        validate_rule(name, cost)

        self.app = app
        self.name = name
        self.policy = policy
        self.identity = identity
        self.cost = cost
        self.exclude_paths = frozenset(exclude_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") == "OPTIONS"
            or scope.get("path") in self.exclude_paths
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        limiter = get_rate_limiter(request)

        result = await limiter.acquire(
            key=build_rate_limit_key(self.name, self.identity(request)),
            policy=self.policy,
            cost=self.cost,
        )

        if not result.allowed:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
                headers=rejection_headers(result),
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
