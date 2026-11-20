from __future__ import annotations

import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import (
    advisor,
    alerts,
    automation,
    auth,
    documents,
    financials,
    fraud,
    market,
    market_outlook,
    money,
    records,
    reports,
    simulator,
    trading,
    verification,
)
from app.config import get_settings
from app.core.logging import configure_logging
from app.db.seed import ensure_demo_data
from app.db.session import AsyncSessionLocal, init_models
from app.db.models import Document, DocumentChunkRow
from app.db.tenant import demo_business_id
from app.llm.factory import build_llm_router
from app.rag.vectorstore import InMemoryVectorStore
from app.rag.vectorstore import DocumentChunk
from app.services.market_data import (
    DemoMarketDataProvider,
    MarketDataService,
    YahooChartProvider,
    YFinanceProvider,
)


async def _periodic_n8n_monitor_task(settings):
    """Background automated financial monitoring worker matching n8n's scheduled cron.

    Periodically scans business financials, updates the in-app alert feed,
    and dispatches webhooks to n8n when reachable.
    """
    await asyncio.sleep(5)  # brief initial delay
    while True:
        try:
            await alerts.evaluate_and_dispatch_alerts(demo_business_id(), settings)
        except Exception:
            pass
        await asyncio.sleep(120)  # runs every 2 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.ENV)

    # Swap InMemoryVectorStore for the Supabase-pgvector-backed store in
    # production (same VectorStore interface — see app/rag/vectorstore.py).
    app.state.vector_store = InMemoryVectorStore()
    app.state.llm_router = build_llm_router(settings)
    app.state.market_service = MarketDataService(
        YahooChartProvider(), YFinanceProvider(), DemoMarketDataProvider()
    )

    await init_models()
    async with AsyncSessionLocal() as session:
        await ensure_demo_data(session)
        # Rehydrate the local index from persisted chunks after a restart.
        # Without this, an upload would appear to succeed but disappear from
        # RAG after the process was recycled.
        rows = (await session.execute(
            select(DocumentChunkRow, Document)
            .join(Document, Document.id == DocumentChunkRow.document_id)
            .where(Document.status == "processed")
        )).all()
        app.state.vector_store.upsert([
            DocumentChunk(
                id=chunk.id,
                text=chunk.text,
                source=document.filename,
                metadata={
                    "business_id": document.business_id,
                    "document_id": document.id,
                    "filename": document.filename,
                    "chunk_index": chunk.chunk_index,
                    "source_location": chunk.source_location,
                },
            )
            for chunk, document in rows
        ])

    monitor_task = asyncio.create_task(_periodic_n8n_monitor_task(settings))

    yield

    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-powered business financial intelligence & decision support.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=r"^https://.*(\.onrender\.com|\.vercel\.app)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.API_V1_PREFIX
    app.include_router(auth.router, prefix=prefix)
    app.include_router(financials.router, prefix=prefix)
    app.include_router(records.router, prefix=prefix)
    app.include_router(simulator.router, prefix=prefix)
    app.include_router(advisor.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(market.router, prefix=prefix)
    app.include_router(market_outlook.router, prefix=prefix)
    app.include_router(trading.router, prefix=prefix)
    app.include_router(money.router, prefix=prefix)
    app.include_router(fraud.router, prefix=prefix)
    app.include_router(verification.router, prefix=prefix)
    app.include_router(automation.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)
    app.include_router(alerts.router, prefix=prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "service": settings.APP_NAME}


    return app


app = create_app()
