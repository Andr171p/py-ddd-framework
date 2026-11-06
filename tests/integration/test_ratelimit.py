"""Execute the production Lua scripts. Install fakeredis[lua] to run these tests."""

import asyncio
import unittest
from datetime import timedelta
from unittest.mock import patch

try:
    import lupa
    from fakeredis.aioredis import FakeRedis
except ImportError:
    FakeRedis = None

from ddf.ratelimit import FixedWindowPolicy, SlidingWindowPolicy, TokenBucketPolicy
from ddf.ratelimit.redis import RedisRateLimiter


@unittest.skipIf(FakeRedis is None, "Install fakeredis[lua] to execute Lua integration tests")
class RedisRateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = FakeRedis()
        self.limiter = RedisRateLimiter(self.redis, prefix="test")

    async def asyncTearDown(self):
        await self.redis.aclose()

    async def acquire_at(self, seconds, policy, *, cost=1, key="user"):
        # Freeze Redis TIME and key expiration without sleeping at window boundaries.
        with patch("time.time", return_value=1_700_000_000 + seconds):
            return await self.limiter.acquire(key, policy, cost=cost)

    async def test_token_bucket_refills_and_expires(self):
        policy = TokenBucketPolicy(capacity=2, refill_rate=2)
        self.assertTrue((await self.acquire_at(0, policy, cost=2)).allowed)
        rejected = await self.acquire_at(0, policy)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.retry_after, timedelta(milliseconds=500))
        self.assertFalse((await self.acquire_at(0.25, policy)).allowed)
        self.assertTrue((await self.acquire_at(0.5, policy)).allowed)
        self.assertEqual((await self.acquire_at(2, policy)).remaining, 1)

    async def test_fixed_window_resets_at_boundary(self):
        policy = FixedWindowPolicy(limit=2, window=timedelta(seconds=1))
        self.assertTrue((await self.acquire_at(0.25, policy, cost=2)).allowed)
        rejected = await self.acquire_at(0.5, policy)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.retry_after, timedelta(milliseconds=500))
        self.assertTrue((await self.acquire_at(1, policy, cost=2)).allowed)

    async def test_sliding_window_previous_counter_decays(self):
        policy = SlidingWindowPolicy(limit=2, window=timedelta(seconds=1))
        self.assertTrue((await self.acquire_at(0, policy, cost=2)).allowed)
        rejected = await self.acquire_at(1, policy)
        self.assertFalse(rejected.allowed)
        self.assertEqual(rejected.retry_after, timedelta(milliseconds=500))
        self.assertTrue((await self.acquire_at(1.5, policy)).allowed)
        self.assertTrue((await self.acquire_at(4, policy, cost=2)).allowed)

    async def test_sliding_window_retry_includes_next_window_decay(self):
        policy = SlidingWindowPolicy(limit=2, window=timedelta(seconds=1))
        await self.acquire_at(0.25, policy, cost=2)
        rejected = await self.acquire_at(0.5, policy)
        self.assertEqual(rejected.retry_after, timedelta(seconds=1))
        self.assertTrue((await self.acquire_at(1.5, policy)).allowed)

    async def test_denied_requests_do_not_consume_capacity(self):
        for policy in (
            TokenBucketPolicy(capacity=2, refill_rate=2),
            FixedWindowPolicy(limit=2, window=timedelta(seconds=1)),
            SlidingWindowPolicy(limit=2, window=timedelta(seconds=1)),
        ):
            with self.subTest(algorithm=policy.algorithm):
                self.assertTrue((await self.acquire_at(0, policy)).allowed)
                self.assertFalse((await self.acquire_at(0, policy, cost=2)).allowed)
                self.assertTrue((await self.acquire_at(0, policy)).allowed)

    async def test_script_flush_is_recovered_by_redis_client(self):
        policy = TokenBucketPolicy(capacity=2, refill_rate=2)
        await self.acquire_at(0, policy)
        await self.redis.script_flush()
        self.assertEqual((await self.acquire_at(0, policy)).remaining, 0)

    async def test_concurrent_requests_obey_each_limit(self):
        limit = 5
        for policy in (
            TokenBucketPolicy(capacity=limit, refill_rate=0.001),
            FixedWindowPolicy(limit=limit, window=timedelta(minutes=1)),
            SlidingWindowPolicy(limit=limit, window=timedelta(minutes=1)),
        ):
            with self.subTest(algorithm=policy.algorithm), patch("time.time", return_value=1_700_000_000):
                results = await asyncio.gather(
                    *(self.limiter.acquire("concurrent", policy) for _ in range(20))
                )
                self.assertEqual(sum(result.allowed for result in results), limit)


if __name__ == "__main__":
    unittest.main()
