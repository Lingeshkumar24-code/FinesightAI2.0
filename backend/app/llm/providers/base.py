"""
Common interface every LLM provider adapter must implement. Keeping this
tiny and synchronous-in-spirit (one async method) is what makes the
router provider-agnostic: swap Gemini for Ollama without touching any
caller.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Raised by a provider adapter on any failure (HTTP error, timeout,
    malformed response, rate limit, etc). The router treats ANY
    ProviderError as a signal to fail over to the next provider."""


@dataclass
class CompletionRequest:
    prompt: str
    system: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024


@dataclass
class CompletionResponse:
    text: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion or raise ProviderError."""
        raise NotImplementedError
