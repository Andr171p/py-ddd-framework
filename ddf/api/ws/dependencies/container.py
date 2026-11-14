from typing import Annotated, cast

from dataclasses import dataclass

from fastapi import Depends, WebSocket

from ddf.api.ws.config import WsConfig
from ddf.application.limits import ConcurrencyLimiter
from ddf.application.realtime import ConnectionManager
from ddf.ratelimit import RateLimiter


@dataclass(frozen=True, slots=True)
class WsContainer:
    config: WsConfig
    connection_manager: ConnectionManager
    rate_limiter: RateLimiter
    concurrency_limiter: ConcurrencyLimiter


def get_ws_container(websocket: WebSocket) -> WsContainer:
    return cast(WsContainer, websocket.state["ws"])


Ws = Annotated[WsContainer, Depends(get_ws_container)]

__all__ = ["Ws", "get_ws_container"]
