import uuid
from importlib.resources import files

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from ddf.application.limits.policies import ConcurrencyPolicy

from .concurrency_lease import RedisConcurrencyLease

_ACQUIRE_LUA = (
    files("ddf.infra.limits.concurrency.redis").joinpath("scripts", "acquire.lua").read_text(encoding="utf-8")
)
_RENEW_LUA = (
    files("ddf.infra.limits.concurrency.redis").joinpath("scripts", "renew.lua").read_text(encoding="utf-8")
)
_RELEASE_LUA = (
    files("ddf.infra.limits.concurrency.redis").joinpath("scripts", "release.lua").read_text(encoding="utf-8")
)


class RedisConcurrencyLimiter:
    def __init__(self, redis: Redis, *, prefix: str = "ddf:concurrency") -> None:
        self._redis = redis
        self._prefix = prefix

        self._acquire_script = redis.register_script(_ACQUIRE_LUA)
        self._renew_script = redis.register_script(_RENEW_LUA)
        self._release_script = redis.register_script(_RELEASE_LUA)

    @property
    def renew_script(self) -> AsyncScript:
        return self._renew_script

    @property
    def release_script(self) -> AsyncScript:
        return self._release_script

    async def acquire(self, key: str, policy: ConcurrencyPolicy) -> RedisConcurrencyLease | None:
        if not key.strip():
            raise ValueError("key must not be empty")

        redis_key = f"{self._prefix}:{key}"
        lease_id = uuid.uuid4().hex
        ttl_ms = int(policy.lease_ttl.total_seconds() * 1000)

        if ttl_ms < 1:
            raise ValueError("lease_ttl must be >= 1ms")

        acquired = await self._acquire_script(keys=[redis_key], args=[lease_id, policy.limit, ttl_ms])
        if not acquired:
            return None

        return RedisConcurrencyLease(
            limiter=self,
            key=redis_key,
            lease_id=lease_id,
            ttl_ms=ttl_ms,
        )
