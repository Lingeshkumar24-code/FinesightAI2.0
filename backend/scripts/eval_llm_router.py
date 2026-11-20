#!/usr/bin/env python
"""
LLMOps evaluation harness for the model-agnostic AI router.

This is NOT a correctness grader for model outputs (that needs real API
keys and a labeled eval set, which is out of scope for this repo). It
IS a reliability/fallback-behavior harness you can run in CI or on a
schedule against a real router config to answer:

  * Given current provider priority, how often does the router fall
    back, and to which provider?
  * What's the added latency when the primary provider is slow/down?
  * Does the router still return SOMETHING for every one of a fixed set
    of representative business questions, even under induced failures?

Run:
    python scripts/eval_llm_router.py

Extend this with real provider credentials wired through
app.llm.factory.build_llm_router to turn it into a live canary check
you run against staging before promoting a provider-priority change.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.providers.base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError
from app.llm.router import AllProvidersFailedError, LLMRouter

SCENARIOS = [
    "What was our budget variance last quarter?",
    "What's our current WACC?",
    "Are there any risk flags I should know about?",
    "Forecast our revenue for the next 3 months.",
    "What if we raise prices by 5%?",
]


class _ScenarioProvider(LLMProvider):
    """Fails on its first N calls (simulating an outage), then recovers —
    used here to exercise the router's fallback path deterministically."""

    def __init__(self, name: str, fail_first_n_calls: int = 0) -> None:
        self.name = name
        self.fail_first_n_calls = fail_first_n_calls
        self.calls = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls += 1
        await asyncio.sleep(0.01)  # simulate network latency
        if self.calls <= self.fail_first_n_calls:
            raise ProviderError(f"{self.name} simulated outage (call {self.calls})")
        return CompletionResponse(
            text=f"[{self.name}] simulated answer to: {request.prompt[:40]}",
            provider=self.name,
            model="eval-stub",
            latency_ms=10.0,
        )


@dataclass
class ScenarioResult:
    scenario: str
    succeeded: bool
    served_by: str | None
    attempts: int
    total_latency_ms: float


async def run_eval() -> list[ScenarioResult]:
    # Simulated topology: primary provider is flaky for the first 2 calls,
    # secondary is healthy, tertiary never needed.
    primary = _ScenarioProvider("primary_gemini", fail_first_n_calls=2)
    secondary = _ScenarioProvider("secondary_openai")
    tertiary = _ScenarioProvider("tertiary_ollama")
    router = LLMRouter(
        providers=[primary, secondary, tertiary],
        max_retries_per_provider=1,
        backoff_base_seconds=0,
    )

    results: list[ScenarioResult] = []
    for scenario in SCENARIOS:
        started = time.perf_counter()
        try:
            result = await router.complete(CompletionRequest(prompt=scenario))
            results.append(
                ScenarioResult(
                    scenario=scenario,
                    succeeded=True,
                    served_by=result.response.provider,
                    attempts=len(result.attempts),
                    total_latency_ms=(time.perf_counter() - started) * 1000,
                )
            )
        except AllProvidersFailedError:
            results.append(
                ScenarioResult(
                    scenario=scenario,
                    succeeded=False,
                    served_by=None,
                    attempts=0,
                    total_latency_ms=(time.perf_counter() - started) * 1000,
                )
            )
    return results


def main() -> None:
    results = asyncio.run(run_eval())
    success_rate = sum(1 for r in results if r.succeeded) / len(results) * 100
    print(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\nSuccess rate: {success_rate:.0f}% ({len(results)} scenarios)")
    if success_rate < 100:
        sys.exit(1)  # non-zero exit fails a CI gate on reliability regressions


if __name__ == "__main__":
    main()
