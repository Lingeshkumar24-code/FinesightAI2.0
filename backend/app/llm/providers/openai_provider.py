from __future__ import annotations

import time

import httpx

from .base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 20.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._base_url = "https://api.openai.com/v1/chat/completions"

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
            raise ProviderError(f"OpenAI provider failed: {exc}") from exc

        if not isinstance(text, str) or not text.strip():
            raise ProviderError("OpenAI returned an empty completion")

        latency_ms = (time.perf_counter() - started) * 1000
        return CompletionResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
