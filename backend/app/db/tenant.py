from __future__ import annotations

from app.config import get_settings

POSTGRES_DEMO_BUSINESS_ID = "00000000-0000-0000-0000-000000000001"
SQLITE_DEMO_BUSINESS_ID = "demo-business-001"


def demo_business_id() -> str:
    """Use a UUID tenant key for Supabase and the legacy string locally."""
    return (
        POSTGRES_DEMO_BUSINESS_ID
        if get_settings().DATABASE_URL.startswith("postgresql")
        else SQLITE_DEMO_BUSINESS_ID
    )
