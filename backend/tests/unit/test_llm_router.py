"""
These tests never touch the network. Each fake provider is a tiny
hand-written stand-in for the base.LLMProvider interface, so we are
testing the ROUTER's fallback/retry/logging behaviour in isolation from
any real HTTP call — exactly the kind of thing that should never depend
on a live API key in CI.
"""
from __future__ import annotations

import pytest

from app.llm.providers.base import CompletionRequest, CompletionResponse, LLMProvider, ProviderError
from app.llm.router import AllProvidersFailedError, LLMRouter


class FakeProvider(LLMProvider):
    """A scripted provider: fails `fail_times` times, then succeeds
    (unless always_fail is set, in which case it never succeeds)."""

    def __init__(self, name: str, fail_times: int = 0, always_fail: bool = False) -> None:
        self.name = name
        self.fail_times = fail_times
        self.always_fail = always_fail
        self.calls = 0

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls += 1
        if self.always_fail or self.calls <= self.fail_times:
            raise ProviderError(f"{self.name} simulated failure #{self.calls}")
        return CompletionResponse(
            text=f"response from {self.name}",
            provider=self.name,
            model="fake-model",
            latency_ms=1.0,
        )


@pytest.fixture
def request_() -> CompletionRequest:
    return CompletionRequest(prompt="What's our runway?")


@pytest.mark.asyncio
async def test_primary_provider_success_short_circuits(request_: CompletionRequest):
    primary = FakeProvider("primary")
    backup = FakeProvider("backup")
    router = LLMRouter(providers=[primary, backup], backoff_base_seconds=0)

    result = await router.complete(request_)

    assert result.response.provider == "primary"
    assert backup.calls == 0  # never invoked
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True


@pytest.mark.asyncio
async def test_falls_back_to_second_provider_on_primary_failure(request_: CompletionRequest):
    primary = FakeProvider("primary", always_fail=True)
    backup = FakeProvider("backup")
    router = LLMRouter(
        providers=[primary, backup], max_retries_per_provider=1, backoff_base_seconds=0
    )

    result = await router.complete(request_)

    assert result.response.provider == "backup"
    assert any(a.provider == "primary" and not a.success for a in result.attempts)
    assert any(a.provider == "backup" and a.success for a in result.attempts)


@pytest.mark.asyncio
async def test_retries_transient_failure_before_moving_on(request_: CompletionRequest):
    primary = FakeProvider("primary", fail_times=1)  # fails once, then succeeds
    backup = FakeProvider("backup")
    router = LLMRouter(
        providers=[primary, backup], max_retries_per_provider=2, backoff_base_seconds=0
    )

    result = await router.complete(request_)

    assert result.response.provider == "primary"
    assert primary.calls == 2  # one failure + one success, same provider
    assert backup.calls == 0


@pytest.mark.asyncio
async def test_all_providers_failing_raises_with_full_attempt_log(request_: CompletionRequest):
    primary = FakeProvider("primary", always_fail=True)
    backup = FakeProvider("backup", always_fail=True)
    router = LLMRouter(
        providers=[primary, backup], max_retries_per_provider=2, backoff_base_seconds=0
    )

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await router.complete(request_)

    # 2 providers * 2 retries each = 4 logged attempts, all failures
    assert len(exc_info.value.attempts) == 4
    assert all(not a.success for a in exc_info.value.attempts)


@pytest.mark.asyncio
async def test_router_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        LLMRouter(providers=[])


@pytest.mark.asyncio
async def test_third_provider_used_when_first_two_fail(request_: CompletionRequest):
    p1 = FakeProvider("gemini", always_fail=True)
    p2 = FakeProvider("openai", always_fail=True)
    p3 = FakeProvider("ollama")
    router = LLMRouter(providers=[p1, p2, p3], max_retries_per_provider=1, backoff_base_seconds=0)

    result = await router.complete(request_)

    assert result.response.provider == "ollama"
