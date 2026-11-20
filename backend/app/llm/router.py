"""
Model-Agnostic AI Router
--------------------------
This is the LLMOps heart of FinSight AI, matching the "Model-Agnostic AI
Router" box in the architecture diagram (Provider Selection | Fallback |
Retry | Logging).

Design goals:
  * Caller never imports a specific provider SDK — only `LLMRouter`.
  * A provider's failure (timeout, 5xx, rate limit, malformed response)
    never surfaces to the caller as long as ANY configured provider
    succeeds — the router walks its priority list.
  * Every attempt (success or failure) is logged once, structured, with
    latency, so attempts can be aggregated into provider-reliability
    dashboards later.
  * Retries are per-provider (transient blip) before failing over to the
    next provider (persistent/outage), with exponential backoff.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

from app.llm.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)

logger = structlog.get_logger("finsight.llm_router")


class AllProvidersFailedError(Exception):
    """Raised only when every provider in the chain has been exhausted."""

    def __init__(self, attempts: list["ProviderAttempt"]) -> None:
        self.attempts = attempts
        provider_names = ", ".join(a.provider for a in attempts)
        super().__init__(f"All providers failed: {provider_names}")


@dataclass
class ProviderAttempt:
    provider: str
    attempt_number: int
    success: bool
    error: str | None = None
    latency_ms: float | None = None


@dataclass
class RouterResult:
    response: CompletionResponse
    attempts: list[ProviderAttempt] = field(default_factory=list)


class LLMRouter:
    def __init__(
        self,
        providers: list[LLMProvider],
        max_retries_per_provider: int = 2,
        backoff_base_seconds: float = 0.5,
    ) -> None:
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self.providers = providers
        self.max_retries_per_provider = max_retries_per_provider
        self.backoff_base_seconds = backoff_base_seconds

    async def complete(self, request: CompletionRequest) -> RouterResult:
        attempts: list[ProviderAttempt] = []

        for provider in self.providers:
            for attempt_number in range(1, self.max_retries_per_provider + 1):
                try:
                    response = await provider.complete(request)
                except ProviderError as exc:
                    attempts.append(
                        ProviderAttempt(
                            provider=provider.name,
                            attempt_number=attempt_number,
                            success=False,
                            error=str(exc),
                        )
                    )
                    logger.warning(
                        "llm_provider_attempt_failed",
                        provider=provider.name,
                        attempt=attempt_number,
                        error=str(exc),
                    )
                    if attempt_number < self.max_retries_per_provider:
                        await asyncio.sleep(self.backoff_base_seconds * attempt_number)
                    continue
                else:
                    attempts.append(
                        ProviderAttempt(
                            provider=provider.name,
                            attempt_number=attempt_number,
                            success=True,
                            latency_ms=response.latency_ms,
                        )
                    )
                    logger.info(
                        "llm_provider_attempt_succeeded",
                        provider=provider.name,
                        attempt=attempt_number,
                        latency_ms=round(response.latency_ms, 1),
                    )
                    return RouterResult(response=response, attempts=attempts)

        logger.error(
            "llm_router_all_providers_failed",
            providers=[p.name for p in self.providers],
        )
        raise AllProvidersFailedError(attempts)
