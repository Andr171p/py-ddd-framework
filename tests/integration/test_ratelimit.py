"""Execute the production Lua scripts against fakeredis with controlled time."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("lupa", reason="Install fakeredis[lua] to execute Lua integration tests")
pytest.importorskip("fakeredis", reason="Install fakeredis[lua] to execute Lua integration tests")
from fakeredis.aioredis import FakeRedis

from ddf.ratelimit import FixedWindowPolicy, SlidingWindowPolicy, TokenBucketPolicy
from ddf.ratelimit.redis import RedisRateLimiter

pytestmark = pytest.mark.anyio
CONCURRENT_LIMIT = 5


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def redis():
    client = FakeRedis()
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def limiter(redis):
    return RedisRateLimiter(redis, prefix="test")


@pytest.fixture
def acquire_at(limiter):
    async def acquire(seconds, policy, *, cost=1, key="user"):
        # Freeze Redis TIME and expiry without sleeping at window boundaries.
        with patch("time.time", return_value=1_700_000_000 + seconds):
            return await limiter.acquire(key, policy, cost=cost)

    return acquire


async def test_token_bucket_refills_and_expires(acquire_at):
    policy = TokenBucketPolicy(capacity=2, refill_rate=2)
    assert (await acquire_at(0, policy, cost=2)).allowed
    rejected = await acquire_at(0, policy)
    assert not rejected.allowed
    assert rejected.retry_after == timedelta(milliseconds=500)
    assert not (await acquire_at(0.25, policy)).allowed
    assert (await acquire_at(0.5, policy)).allowed
    assert (await acquire_at(2, policy)).remaining == 1


async def test_fixed_window_resets_at_boundary(acquire_at):
    policy = FixedWindowPolicy(limit=2, window=timedelta(seconds=1))
    assert (await acquire_at(0.25, policy, cost=2)).allowed
    rejected = await acquire_at(0.5, policy)
    assert not rejected.allowed
    assert rejected.retry_after == timedelta(milliseconds=500)
    assert (await acquire_at(1, policy, cost=2)).allowed


async def test_sliding_window_previous_counter_decays(acquire_at):
    policy = SlidingWindowPolicy(limit=2, window=timedelta(seconds=1))
    assert (await acquire_at(0, policy, cost=2)).allowed
    rejected = await acquire_at(1, policy)
    assert not rejected.allowed
    assert rejected.retry_after == timedelta(milliseconds=500)
    assert (await acquire_at(1.5, policy)).allowed
    assert (await acquire_at(4, policy, cost=2)).allowed


async def test_sliding_window_retry_includes_next_window_decay(acquire_at):
    policy = SlidingWindowPolicy(limit=2, window=timedelta(seconds=1))
    await acquire_at(0.25, policy, cost=2)
    rejected = await acquire_at(0.5, policy)
    assert rejected.retry_after == timedelta(seconds=1)
    assert (await acquire_at(1.5, policy)).allowed


@pytest.mark.parametrize(
    "policy",
    [
        TokenBucketPolicy(capacity=2, refill_rate=2),
        FixedWindowPolicy(limit=2, window=timedelta(seconds=1)),
        SlidingWindowPolicy(limit=2, window=timedelta(seconds=1)),
    ],
    ids=lambda policy: policy.algorithm,
)
async def test_denied_requests_do_not_consume_capacity(acquire_at, policy):
    assert (await acquire_at(0, policy)).allowed
    assert not (await acquire_at(0, policy, cost=2)).allowed
    assert (await acquire_at(0, policy)).allowed


async def test_script_flush_is_recovered_by_redis_client(acquire_at, redis):
    policy = TokenBucketPolicy(capacity=2, refill_rate=2)
    await acquire_at(0, policy)
    await redis.script_flush()
    assert (await acquire_at(0, policy)).remaining == 0


@pytest.mark.parametrize(
    "policy",
    [
        TokenBucketPolicy(capacity=CONCURRENT_LIMIT, refill_rate=0.001),
        FixedWindowPolicy(limit=CONCURRENT_LIMIT, window=timedelta(minutes=1)),
        SlidingWindowPolicy(limit=CONCURRENT_LIMIT, window=timedelta(minutes=1)),
    ],
    ids=lambda policy: policy.algorithm,
)
async def test_concurrent_requests_obey_each_limit(limiter, policy):
    with patch("time.time", return_value=1_700_000_000):
        results = await asyncio.gather(*(limiter.acquire("concurrent", policy) for _ in range(20)))
    assert sum(result.allowed for result in results) == CONCURRENT_LIMIT
