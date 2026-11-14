from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from ddf.api.ws import WsContainer


class WsContainerMiddleware:
    def __init__(self, app: ASGIApp, container: WsContainer) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            state: MutableMapping[str, Any] = scope.setdefault("state", {})
            state["ws"] = self.container
        await self.app(scope, receive, send)
