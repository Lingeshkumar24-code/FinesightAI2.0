from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import extensions

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def _ensure_sqlite_columns() -> None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    async with engine.begin() as conn:
        existing = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(financial_records)"))).fetchall()
        }
        definitions = {
            "period_start": "TEXT DEFAULT ''",
            "period_end": "TEXT DEFAULT ''",
            "cash": "FLOAT",
            "accounts_receivable": "FLOAT",
            "inventory": "FLOAT",
            "other_current_assets": "FLOAT",
            "total_current_assets": "FLOAT",
            "total_current_liabilities": "FLOAT",
            "short_term_debt": "FLOAT",
            "long_term_debt": "FLOAT",
            "interest_expense": "FLOAT",
            "ebit": "FLOAT",
            "operating_cash_flow": "FLOAT",
            "investing_cash_flow": "FLOAT",
            "financing_cash_flow": "FLOAT",
            "opening_cash": "FLOAT",
            "closing_cash": "FLOAT",
            "source": "TEXT DEFAULT 'manual'",
            "source_document_id": "TEXT DEFAULT ''",
            "verified": "BOOLEAN DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
        }
        for name, definition in definitions.items():
            if name not in existing:
                await conn.execute(text(f"ALTER TABLE financial_records ADD COLUMN {name} {definition}"))

        chunk_columns = {
            row[1]
            for row in (await conn.execute(text("PRAGMA table_info(document_chunks)"))).fetchall()
        }
        if "source_location" not in chunk_columns:
            await conn.execute(
                text("ALTER TABLE document_chunks ADD COLUMN source_location TEXT DEFAULT ''")
            )


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(extensions.Base.metadata.create_all)
    await _ensure_sqlite_columns()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def table_exists(name: str) -> bool:
    async with engine.begin() as conn:
        return await conn.run_sync(lambda sync: name in inspect(sync).get_table_names())
