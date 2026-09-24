from typing import Any

import inspect
from collections.abc import Mapping

from openai import AsyncOpenAI

from .analyzer import analyze_response_request
from .model_router import ModelRouter
from .types import TokenEstimator


class RoutedResponses:
    def __init__(
        self,
        *,
        router: ModelRouter,
        clients: Mapping[str, AsyncOpenAI],
        default_provider: str,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        self._router = router
        self._clients = clients
        self._default_provider = default_provider
        self._token_estimator = token_estimator

    async def create(self, **params: Any) -> Any:
        explicit_model = params.get("model")

        if explicit_model is not None:
            return await self._create_explicit(explicit_model, params,)

        input_tokens = await self._estimate_tokens(params)

        routing_request = analyze_response_request(params, estimated_input_tokens=input_tokens)

        model = await self._router.route(routing_request)
        client = self._clients[model.provider]

        return await client.responses.create(model=model.model, **params)

    async def _create_explicit(self, model_id: str, params: dict[str, Any]) -> Any:
        model = self._router.get(model_id)

        if model is None:
            client = self._clients[self._default_provider]
            return await client.responses.create(**params)

        params = {**params, "model": model.model}
        client = self._clients[model.provider]

        return await client.responses.create(**params)

    async def _estimate_tokens(self, params: Mapping[str, Any]) -> int | None:
        if self._token_estimator is None:
            return None

        result = self._token_estimator(params)

        return await result if inspect.isawaitable(result) else result


class RoutedOpenAI:
    def __init__(
        self,
        *,
        router: ModelRouter,
        clients: Mapping[str, AsyncOpenAI],
        default_provider: str,
        token_estimator: TokenEstimator | None = None,
    ) -> None:

        if default_provider not in clients:
            raise ValueError(f"Unknown default provider: {default_provider!r}.")

        self.responses = RoutedResponses(
            router=router,
            clients=clients,
            default_provider=default_provider,
            token_estimator=token_estimator,
        )
        self._clients = clients

    def client(self, provider: str) -> AsyncOpenAI:
        return self._clients[provider]
