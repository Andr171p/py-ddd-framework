from typing import Annotated

import asyncio
import logging
import math
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status

from ddf.application.limits import ConcurrencyLease

from .container import Ws

logger = logging.getLogger(__name__)

type WsAdmitter = Callable[..., AsyncIterator[WsAdmission]]


@dataclass(frozen=True, slots=True)
class WsAdmission:
    """Представляет результат допуска одного соединения."""

    subject_key: str
    lost: asyncio.Event


async def _renew_lease(lease: ConcurrencyLease, lost: asyncio.Event, interval: float) -> None:
    # noinspection PyBroadException
    try:
        while True:
            await asyncio.sleep(interval)

            async with asyncio.timeout(min(2.0, interval / 2)):
                renewed = await lease.renew()

            if not renewed:
                lost.set()
                return

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception("WebSocket lease renewal failed")
        lost.set()


def create_ws_admitter(get_subject_key: Callable[..., str | Awaitable[str]]) -> WsAdmitter:
    async def admit_websocket(
        subject_key: Annotated[str, Depends(get_subject_key)],
        ws: Ws,
    ) -> AsyncIterator[WsAdmission]:
        config = ws.config.admission

        rate = await ws.rate_limiter.acquire(
            key=f"ws:connect:{subject_key}",
            policy=config.connect_rate_policy,
        )
        if not rate.allowed:
            headers: dict[str, str] | None = None
            if rate.retry_after is not None:
                seconds = math.ceil(rate.retry_after.total_seconds())
                headers = {"Retry-After": str(max(1, seconds))}

            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, headers=headers)

        lease = await ws.concurrency_limiter.acquire(
            key=f"ws:active:{subject_key}",
            policy=config.concurrency_policy,
        )
        if lease is None:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)

        lost = asyncio.Event()
        task = asyncio.create_task(
            _renew_lease(lease, lost, interval=config.lease_ttl.total_seconds() / 3),
            name="ws-lease-renewal",
        )

        try:
            yield WsAdmission(subject_key=subject_key, lost=lost)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

            # noinspection PyBroadException
            try:
                await lease.release()
            except Exception:
                logger.exception("Failed to release WebSocket lease")

    return admit_websocket


__all__ = ["WsAdmission", "create_ws_admitter"]
