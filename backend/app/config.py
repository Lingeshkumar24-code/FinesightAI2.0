"""
Centralized settings. All values are overridable via environment
variables / .env (see ../.env.example at the repo root for the full
list with descriptions). Nothing here has a production secret baked
in — every credential defaults to empty string and the app degrades
gracefully (e.g. the LLM router falls back to a template response) when
a given provider's key is absent.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "FinSight AI"
    ENV: str = "development"  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5175",
        "http://localhost:4173",
        "http://localhost:80",
        "http://frontend:80",
        "https://finsight-frontend-2w1v.onrender.com",
    ]

    # --- Auth (JWT issued by this API; swap for Supabase Auth JWKS verification in prod) ---
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24
    ALLOW_DEMO_AUTH: bool = True

    # --- Database (Supabase Postgres in prod; SQLite for local/dev/tests) ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./finsight.db"

    # --- Supabase (production) ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "financial-documents"

    # --- LLM providers (model-agnostic router) ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    # Priority order the router walks, by provider name.
    LLM_PROVIDER_PRIORITY: list[str] = ["gemini", "openai", "openrouter", "ollama"]

    # --- n8n (automation layer) ---
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/finsight-alerts"
    N8N_SHARED_SECRET: str = "finsight-n8n-secret"

    # --- Market data (Twelve Data) ---
    TWELVEDATA_API_KEY: str = ""
    TWELVEDATA_BASE_URL: str = "https://api.twelvedata.com"
    # Comma-separated benchmark watchlist shown on the Market Data page. The
    # free plan costs one credit per symbol with 8 credits/minute, so the
    # default is five symbols: quotes + history + the usage check then cost
    # 7 credits, leaving one spare inside the minute. Kept as a plain string
    # because pydantic-settings would otherwise require the env value to be
    # JSON.
    MARKET_WATCHLIST: str = "TCS.NS,RELIANCE.NS,INFY.NS,HDFCBANK.NS,SBIN.NS"
    MARKET_MAX_SYMBOLS: int = 6

    # Upload guardrail. Large uploads are rejected before extraction so a
    # single request cannot exhaust memory or tie up the API process.
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
