from __future__ import annotations

import time

import httpx

from .base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _url(self) -> str:
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        contents = [{"role": "user", "parts": [{"text": request.prompt}]}]
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self._url(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"Gemini provider failed: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return CompletionResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )
