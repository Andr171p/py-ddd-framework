import hashlib
from datetime import timedelta
from importlib.resources import files

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from ddf.ratelimit.models import RateLimitPolicy, RateLimitResult

from .strategies import ScriptCall, prepare_script_call


class RedisRateLimiter:
    def __init__(self, redis: Redis, *, prefix: str) -> None:
        if not isinstance(prefix, str) or not prefix.strip():
            raise ValueError("prefix must be a non-empty string")

        self._redis = redis
        self._prefix = prefix
        self._scripts: dict[str, AsyncScript] = {}

    def _get_script(self, name: str) -> AsyncScript:
        if (script := self._scripts.get(name)) is None:
            source = files("ddf.ratelimit.redis").joinpath("scripts", name).read_text(encoding="utf-8")
            script = self._redis.register_script(source)
            self._scripts[name] = script

        return script

    def _key(self, key: str, call: ScriptCall) -> str:
        identity = f"{call.script}:{call.signature}"
        version = hashlib.sha256(identity.encode()).hexdigest()[:16]
        return f"{self._prefix}:v2:{version}:{key}"

    async def acquire(self, key: str, policy: RateLimitPolicy, *, cost: int = 1) -> RateLimitResult:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")

        if type(cost) is not int or cost < 1:
            raise ValueError("cost must be a positive integer")

        call = prepare_script_call(policy, cost)

        if cost > call.limit:
            raise ValueError("cost exceeds policy capacity")

        raw = await self._get_script(call.script)(keys=[self._key(key, call)], args=call.args,)
        allowed, remaining, retry_ms = map(int, raw)

        return RateLimitResult(
            allowed=bool(allowed),
            limit=call.limit,
            remaining=remaining,
            retry_after=None if allowed else timedelta(milliseconds=max(1, retry_ms)),
        )
