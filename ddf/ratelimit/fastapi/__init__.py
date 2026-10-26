"""
# DDF FastAPI Rate Limiter

## Endpoint level dependency

```python
router = APIRouter(prefix="/messages")


async def get_current_user_id(
    user: Annotated[AuthUser, Depends(get_auth_user)],
) -> str:
    return str(user.id)


@router.post(
    "",
    dependencies=[
        Depends(
            rate_limit(
                "chat:messages:create",
                TokenBucketPolicy(
                    capacity=20,
                    refill_rate=1,
                ),
                identity=get_current_user_id,
            )
        )
    ],
)
async def create_message(...):
    ...
```

## Application level middleware

```python
from fastapi import FastAPI, Request


def client_ip(request: Request) -> str:
    if request.client is None:
        raise RuntimeError("Client address is unavailable")

    Return request.client.host


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

## Подключение к FastAPI lifespan

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from ddf.ratelimit.redis import RedisRateLimiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url("redis://localhost:6379")

    app.state.rate_limiter = RedisRateLimiter(redis)

    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(lifespan=lifespan)
```

## Нюансы

### CORS

Если приложение использует CORSMiddleware, оно должно оборачивать rate-limiting middleware снаружи,
чтобы даже отклонённые запросы получали необходимые CORS-заголовки.
В FastAPI последний зарегистрированный middleware выполняется первым.
"""

from .common import get_rate_limiter
from .dependencies import rate_limit
from .middlewares import RateLimitMiddleware

__all__ = ["RateLimitMiddleware", "get_rate_limiter", "rate_limit"]
