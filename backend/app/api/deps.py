"""
Shared FastAPI dependencies.

The vector store and LLM router are created once at app startup and
stashed on `app.state` (see main.py's lifespan). Routes/tests read them
back out through these tiny dependency functions, which makes it trivial
to override either one in tests (`app.dependency_overrides[...]`)
without touching route code.
"""
from __future__ import annotations

from fastapi import Request

from app.llm.router import LLMRouter
from app.rag.retriever import Retriever
from app.rag.vectorstore import VectorStore
from app.services.market_data import (
    DemoMarketDataProvider,
    MarketDataService,
    YahooChartProvider,
    YFinanceProvider,
)


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_retriever(request: Request) -> Retriever:
    return Retriever(request.app.state.vector_store)


def get_llm_router(request: Request) -> LLMRouter | None:
    return getattr(request.app.state, "llm_router", None)


def get_market_service(request: Request) -> MarketDataService:
    service = getattr(request.app.state, "market_service", None)
    if service is None:
        service = MarketDataService(
            YahooChartProvider(), YFinanceProvider(), DemoMarketDataProvider()
        )
        request.app.state.market_service = service
    return service
