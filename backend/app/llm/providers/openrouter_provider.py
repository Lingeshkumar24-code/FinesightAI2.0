from __future__ import annotations

import time

import httpx

from .base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError


class OpenRouterProvider(LLMProvider):
    """OpenRouter exposes an OpenAI-compatible chat completions API that
    fans out to many underlying models — used here as the "catch-all"
    fallback provider."""

    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self._base_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"].get("content")
            usage = data.get("usage", {})
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"OpenRouter provider failed: {exc}") from exc

        if not isinstance(text, str) or not text.strip():
            # Some free models answer with null content (e.g. only a
            # reasoning trace). Treat it as a provider failure so the
            # router fails over instead of shipping an empty answer.
            raise ProviderError("OpenRouter returned an empty completion")

        latency_ms = (time.perf_counter() - started) * 1000
        return CompletionResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
