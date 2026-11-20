"""
Builds an `LLMRouter` from application settings, ordering providers by
`LLM_PROVIDER_PRIORITY` and skipping any provider whose required
credential is missing (so a deployment with only an OpenAI key, say,
gets a one-provider router rather than a crash).
"""
from __future__ import annotations

from app.config import Settings
from app.llm.providers.base import LLMProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.openrouter_provider import OpenRouterProvider
from app.llm.router import LLMRouter


def _build_available_providers(settings: Settings) -> dict[str, LLMProvider]:
    available: dict[str, LLMProvider] = {}
    if settings.GEMINI_API_KEY:
        available["gemini"] = GeminiProvider(settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    if settings.OPENAI_API_KEY:
        available["openai"] = OpenAIProvider(settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    if settings.OPENROUTER_API_KEY:
        available["openrouter"] = OpenRouterProvider(
            settings.OPENROUTER_API_KEY, model=settings.OPENROUTER_MODEL
        )
    # Ollama needs no API key — it's reachable as long as the base URL
    # resolves, so it's always offered as the final, self-hosted fallback.
    available["ollama"] = OllamaProvider(settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL)
    return available


def build_llm_router(settings: Settings) -> LLMRouter | None:
    available = _build_available_providers(settings)
    ordered = [
        available[name] for name in settings.LLM_PROVIDER_PRIORITY if name in available
    ]
    if not ordered:
        return None
    return LLMRouter(providers=ordered)
