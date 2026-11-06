"""Unit and FastAPI tests for rate limiting."""

import inspect
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Depends, FastAPI, Request, status
from httpx import ASGITransport, AsyncClient

from ddf.ratelimit import FixedWindowPolicy, RateLimiter, RateLimitResult, TokenBucketPolicy
from ddf.ratelimit.fastapi import RateLimitMiddleware, rate_limit
from ddf.ratelimit.fastapi.common import build_rate_limit_key
from ddf.ratelimit.models import BaseRateLimitPolicy, SlidingWindowPolicy
from ddf.ratelimit.redis import RedisRateLimiter
from ddf.ratelimit.redis.strategies import prepare_script_call

CAPACITY = 2


def policies():
    return (
        TokenBucketPolicy(capacity=2, refill_rate=2),
        FixedWindowPolicy(limit=2, window=timedelta(seconds=1)),
        SlidingWindowPolicy(limit=2, window=timedelta(seconds=1)),
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def limiter_setup():
    script = AsyncMock(return_value=[1, 1, 0])
    redis = Mock()
    redis.register_script.return_value = script
    return RedisRateLimiter(redis, prefix="test"), redis, script


@pytest.mark.parametrize("policy", policies(), ids=lambda policy: policy.algorithm)
def test_builtin_strategies_are_registered_on_import(policy):
    call = prepare_script_call(policy, 1)
    assert call.script == f"{policy.algorithm}.lua"
    assert call.limit == CAPACITY
    assert call.args[2] == 1


def test_unsupported_policy_is_rejected():
    with pytest.raises(ValueError, match="Unsupported rate limit policy"):
        prepare_script_call(BaseRateLimitPolicy(algorithm="unknown"), 1)


def test_protocol_default_matches_implementation():
    assert (
        inspect.signature(RateLimiter.acquire).parameters["cost"].default
        == inspect.signature(RedisRateLimiter.acquire).parameters["cost"].default
    )


def test_rule_names_and_identities_with_colons_do_not_collide():
    assert build_rate_limit_key("api", "1:a") != build_rate_limit_key("api:3", "a")


@pytest.mark.anyio
async def test_all_script_resources_can_be_loaded_and_cached(limiter_setup):
    limiter, redis, _ = limiter_setup
    for policy in policies():
        assert await limiter.acquire("user", policy) == RateLimitResult(True, 2, 1)
        await limiter.acquire("user", policy)
    assert redis.register_script.call_count == len(policies())
    for call in redis.register_script.call_args_list:
        assert 'redis.call("TIME")' in call.args[0]


@pytest.mark.anyio
async def test_rejected_request_has_retry_duration(limiter_setup):
    limiter, _, script = limiter_setup
    script.return_value = [0, 0, 1250]
    assert await limiter.acquire("user", policies()[0]) == RateLimitResult(
        False, 2, 0, timedelta(milliseconds=1250)
    )


@pytest.mark.anyio
@pytest.mark.parametrize("key", ["", None, 1])
async def test_invalid_key_does_not_touch_redis(limiter_setup, key):
    limiter, redis, _ = limiter_setup
    with pytest.raises(ValueError):
        await limiter.acquire(key, policies()[0])
    redis.register_script.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("cost", [0, -1, True, 1.5, 3])
async def test_invalid_cost_does_not_touch_redis(limiter_setup, cost):
    limiter, redis, _ = limiter_setup
    with pytest.raises(ValueError):
        await limiter.acquire("user", policies()[0], cost=cost)
    redis.register_script.assert_not_called()


@pytest.mark.anyio
async def test_policy_and_identity_separate_state_but_cost_does_not(limiter_setup):
    limiter, _, script = limiter_setup
    keys = []
    for policy in (*policies(), TokenBucketPolicy(capacity=3, refill_rate=2)):
        await limiter.acquire("user", policy)
        keys.append(script.call_args.kwargs["keys"][0])
    assert len(set(keys)) == len(keys)
    await limiter.acquire("user", policies()[0], cost=2)
    assert script.call_args.kwargs["keys"][0] == keys[0]
    await limiter.acquire("other", policies()[0])
    assert script.call_args.kwargs["keys"][0] != keys[0]


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["sync_dependency", "async_dependency", "middleware"])
async def test_fastapi_rate_limit_and_exclusions(mode):
    app = FastAPI()
    limiter = AsyncMock()
    limiter.acquire.side_effect = (
        RateLimitResult(True, 2, 0),
        RateLimitResult(False, 2, 0, timedelta(milliseconds=1001)),
    )
    app.state.rate_limiter = limiter

    def identity(request: Request) -> str:
        return request.headers["X-User"]

    async def get_identity(request: Request) -> str:
        return identity(request)

    if mode == "middleware":
        app.add_middleware(
            RateLimitMiddleware,
            name="api",
            policy=policies()[0],
            identity=identity,
            exclude_paths=("/health",),
        )
        dependencies = []
    else:
        dependencies = [
            Depends(
                rate_limit(
                    "api", policies()[0], identity=get_identity if mode == "async_dependency" else identity
                )
            )
        ]

    @app.get("/", dependencies=dependencies)
    async def endpoint():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/", headers={"X-User": "alice"})).status_code == status.HTTP_200_OK
        response = await client.get("/", headers={"X-User": "alice"})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json() == {"detail": "Rate limit exceeded"}
        assert response.headers["retry-after"] == "2"
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get("/health")).status_code == status.HTTP_200_OK
        if mode == "middleware":
            await client.options("/")
        expected_calls = 2
        assert limiter.acquire.await_count == expected_calls
        limiter.acquire.assert_awaited_with(key="3:api:5:alice", policy=policies()[0], cost=1)
