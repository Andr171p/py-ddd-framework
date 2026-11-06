import inspect
import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

from fastapi import Depends, FastAPI, Request
from httpx import ASGITransport, AsyncClient

from ddf.ratelimit import FixedWindowPolicy, RateLimiter, RateLimitResult, TokenBucketPolicy
from ddf.ratelimit.fastapi import RateLimitMiddleware, rate_limit
from ddf.ratelimit.fastapi.common import build_rate_limit_key
from ddf.ratelimit.models import BaseRateLimitPolicy, SlidingWindowPolicy
from ddf.ratelimit.redis import RedisRateLimiter
from ddf.ratelimit.redis.strategies import prepare_script_call


def policies():
    return (
        TokenBucketPolicy(capacity=2, refill_rate=2),
        FixedWindowPolicy(limit=2, window=timedelta(seconds=1)),
        SlidingWindowPolicy(limit=2, window=timedelta(seconds=1)),
    )


class StrategyTests(unittest.TestCase):
    def test_builtin_strategies_are_registered_on_import(self):
        for policy in policies():
            with self.subTest(algorithm=policy.algorithm):
                call = prepare_script_call(policy, 1)
                self.assertEqual(call.script, f"{policy.algorithm}.lua")
                self.assertEqual(call.limit, 2)
                self.assertEqual(call.args[2], 1)

    def test_unsupported_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported rate limit policy"):
            prepare_script_call(BaseRateLimitPolicy(algorithm="unknown"), 1)

    def test_protocol_default_matches_implementation(self):
        self.assertEqual(
            inspect.signature(RateLimiter.acquire).parameters["cost"].default,
            inspect.signature(RedisRateLimiter.acquire).parameters["cost"].default,
        )

    def test_rule_names_and_identities_with_colons_do_not_collide(self):
        self.assertNotEqual(
            build_rate_limit_key("api", "1:a"),
            build_rate_limit_key("api:3", "a"),
        )


class LimiterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.script = AsyncMock(return_value=[1, 1, 0])
        self.redis = Mock()
        self.redis.register_script.return_value = self.script
        self.limiter = RedisRateLimiter(self.redis, prefix="test")

    async def test_all_script_resources_can_be_loaded_and_cached(self):
        for policy in policies():
            with self.subTest(algorithm=policy.algorithm):
                result = await self.limiter.acquire("user", policy)
                self.assertEqual(result, RateLimitResult(True, 2, 1))
                await self.limiter.acquire("user", policy)
        self.assertEqual(self.redis.register_script.call_count, len(policies()))
        for call in self.redis.register_script.call_args_list:
            self.assertIn('redis.call("TIME")', call.args[0])

    async def test_rejected_request_has_retry_duration(self):
        self.script.return_value = [0, 0, 1250]
        result = await self.limiter.acquire("user", policies()[0])
        self.assertEqual(result, RateLimitResult(False, 2, 0, timedelta(milliseconds=1250)))

    async def test_invalid_inputs_do_not_touch_redis(self):
        for key in ("", None, 1):
            with self.subTest(key=key), self.assertRaises(ValueError):
                await self.limiter.acquire(key, policies()[0])
        for cost in (0, -1, True, 1.5, 3):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                await self.limiter.acquire("user", policies()[0], cost=cost)
        self.redis.register_script.assert_not_called()

    async def test_policy_and_identity_separate_state_but_cost_does_not(self):
        keys = []
        for policy in (*policies(), TokenBucketPolicy(capacity=3, refill_rate=2)):
            await self.limiter.acquire("user", policy)
            keys.append(self.script.call_args.kwargs["keys"][0])
        self.assertEqual(len(set(keys)), len(keys))
        await self.limiter.acquire("user", policies()[0], cost=2)
        self.assertEqual(self.script.call_args.kwargs["keys"][0], keys[0])
        await self.limiter.acquire("other", policies()[0])
        self.assertNotEqual(self.script.call_args.kwargs["keys"][0], keys[0])


class FastAPITests(unittest.IsolatedAsyncioTestCase):
    async def check_integration(self, *, middleware, async_identity=False):
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

        if middleware:
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
                    rate_limit("api", policies()[0], identity=get_identity if async_identity else identity)
                )
            ]

        @app.get("/", dependencies=dependencies)
        async def endpoint():
            return {"ok": True}

        @app.get("/health")
        async def health():
            return {"ok": True}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            self.assertEqual((await client.get("/", headers={"X-User": "alice"})).status_code, 200)
            response = await client.get("/", headers={"X-User": "alice"})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json(), {"detail": "Rate limit exceeded"})
            self.assertEqual(response.headers["retry-after"], "2")
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual((await client.get("/health")).status_code, 200)
            if middleware:
                await client.options("/")
            self.assertEqual(limiter.acquire.await_count, 2)
            limiter.acquire.assert_awaited_with(key="3:api:5:alice", policy=policies()[0], cost=1)

    async def test_dependency_with_sync_identity(self):
        await self.check_integration(middleware=False)

    async def test_dependency_with_async_identity(self):
        await self.check_integration(middleware=False, async_identity=True)

    async def test_middleware_and_exclusions(self):
        await self.check_integration(middleware=True)


if __name__ == "__main__":
    unittest.main()
