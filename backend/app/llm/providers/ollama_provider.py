from __future__ import annotations

import time

import httpx

from .base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError


class OllamaProvider(LLMProvider):
    """Local/self-hosted model, typically the last-resort fallback so the
    advisor keeps working even if every paid provider is down or the
    business has no API keys configured at all."""

    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        prompt = request.prompt
        if request.system:
            prompt = f"{request.system}\n\n{request.prompt}"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens,
                        },
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            text = data["response"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"Ollama provider failed: {exc}") from exc

        latency_ms = (time.perf_counter() - started) * 1000
        return CompletionResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )
