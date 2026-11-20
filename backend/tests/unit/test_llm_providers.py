"""
Unlike test_llm_router.py (which uses hand-written fakes to test the
ROUTER), these tests mock the actual HTTP boundary with `respx` to
verify each PROVIDER ADAPTER parses its specific API's response shape
correctly and raises ProviderError on failure — still zero real network
calls, zero API keys needed, safe for CI.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.llm.providers.base import CompletionRequest, ProviderError
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.openrouter_provider import OpenRouterProvider


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_parses_success_response():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Your runway is 6 months."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )
    provider = OpenAIProvider(api_key="fake-key")
    result = await provider.complete(CompletionRequest(prompt="What's our runway?"))
    assert result.text == "Your runway is 6 months."
    assert result.provider == "openai"
    assert result.input_tokens == 10


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_raises_provider_error_on_5xx():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="internal error")
    )
    provider = OpenAIProvider(api_key="fake-key")
    with pytest.raises(ProviderError):
        await provider.complete(CompletionRequest(prompt="hello"))


@pytest.mark.asyncio
@respx.mock
async def test_gemini_provider_parses_success_response():
    respx.post(url__regex=r"https://generativelanguage\.googleapis\.com/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Net margin is 12%."}]}}],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
            },
        )
    )
    provider = GeminiProvider(api_key="fake-key")
    result = await provider.complete(CompletionRequest(prompt="What's our net margin?"))
    assert result.text == "Net margin is 12%."
    assert result.provider == "gemini"


@pytest.mark.asyncio
@respx.mock
async def test_gemini_provider_raises_on_malformed_response():
    respx.post(url__regex=r"https://generativelanguage\.googleapis\.com/.*").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    provider = GeminiProvider(api_key="fake-key")
    with pytest.raises(ProviderError):
        await provider.complete(CompletionRequest(prompt="hello"))


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_parses_success_response():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "Breakeven in month 4."}}]}
        )
    )
    provider = OpenRouterProvider(api_key="fake-key")
    result = await provider.complete(CompletionRequest(prompt="When do we break even?"))
    assert result.text == "Breakeven in month 4."
    assert result.provider == "openrouter"


@pytest.mark.asyncio
@respx.mock
async def test_ollama_provider_parses_success_response():
    respx.post("http://localhost:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "Local model says: looks healthy."})
    )
    provider = OllamaProvider(base_url="http://localhost:11434")
    result = await provider.complete(CompletionRequest(prompt="How are we doing?"))
    assert "healthy" in result.text
    assert result.provider == "ollama"


@pytest.mark.asyncio
@respx.mock
async def test_ollama_provider_raises_on_connection_error():
    respx.post("http://localhost:11434/api/generate").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    provider = OllamaProvider(base_url="http://localhost:11434")
    with pytest.raises(ProviderError):
        await provider.complete(CompletionRequest(prompt="hello"))

@pytest.mark.asyncio
@respx.mock
async def test_openrouter_provider_treats_null_content_as_failure():
    # Some free models answer with null content (reasoning-only responses).
    # The router must fail over instead of shipping an empty answer.
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
    )
    provider = OpenRouterProvider(api_key="fake-key")
    with pytest.raises(ProviderError):
        await provider.complete(CompletionRequest(prompt="Summarise my cash flow"))


@pytest.mark.asyncio
@respx.mock
async def test_openai_provider_treats_null_content_as_failure():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
    )
    provider = OpenAIProvider(api_key="fake-key")
    with pytest.raises(ProviderError):
        await provider.complete(CompletionRequest(prompt="Summarise my cash flow"))
