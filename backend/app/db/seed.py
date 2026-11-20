from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.extensions import Budget, CashFlowRecord, CapitalStructureRecord, ExpenseRecord
from app.db.models import Business, FinancialRecord
from app.db.tenant import demo_business_id

DEMO_BUSINESS_ID = demo_business_id()

_DEMO_PERIODS = [
    {
        "period": "2026-Q1",
        "revenue": 268000.0,
        "cogs": 106000.0,
        "operating_expenses": 88000.0,
        "net_income": 48000.0,
        "total_assets": 252000.0,
        "total_liabilities": 96000.0,
        "total_equity": 156000.0,
        "cash": 54000.0,
        "accounts_receivable": 22000.0,
        "inventory": 10000.0,
        "other_current_assets": 4000.0,
        "total_current_assets": 90000.0,
        "total_current_liabilities": 44000.0,
        "short_term_debt": 20000.0,
        "long_term_debt": 76000.0,
        "interest_expense": 1800.0,
        "ebit": 74000.0,
        "operating_cash_flow": 22000.0,
        "investing_cash_flow": -8000.0,
        "financing_cash_flow": -4000.0,
        "opening_cash": 44000.0,
        "closing_cash": 54000.0,
    },
    {
        "period": "2026-Q2",
        "revenue": 292000.0,
        "cogs": 112000.0,
        "operating_expenses": 91000.0,
        "net_income": 53000.0,
        "total_assets": 266000.0,
        "total_liabilities": 94000.0,
        "total_equity": 172000.0,
        "cash": 58000.0,
        "accounts_receivable": 23000.0,
        "inventory": 10500.0,
        "other_current_assets": 4000.0,
        "total_current_assets": 95500.0,
        "total_current_liabilities": 45000.0,
        "short_term_debt": 19000.0,
        "long_term_debt": 75000.0,
        "interest_expense": 1750.0,
        "ebit": 81000.0,
        "operating_cash_flow": 25000.0,
        "investing_cash_flow": -9000.0,
        "financing_cash_flow": -5000.0,
        "opening_cash": 54000.0,
        "closing_cash": 58000.0,
    },
    {
        "period": "2026-Q3",
        "revenue": 310000.0,
        "cogs": 118000.0,
        "operating_expenses": 94000.0,
        "net_income": 58000.0,
        "total_assets": 280000.0,
        "total_liabilities": 98000.0,
        "total_equity": 182000.0,
        "cash": 62000.0,
        "accounts_receivable": 24000.0,
        "inventory": 11000.0,
        "other_current_assets": 4000.0,
        "total_current_assets": 101000.0,
        "total_current_liabilities": 46000.0,
        "short_term_debt": 18000.0,
        "long_term_debt": 80000.0,
        "interest_expense": 1900.0,
        "ebit": 92000.0,
        "operating_cash_flow": 27000.0,
        "investing_cash_flow": -10000.0,
        "financing_cash_flow": -6000.0,
        "opening_cash": 58000.0,
        "closing_cash": 62000.0,
    },
]


async def ensure_demo_data(session: AsyncSession) -> None:
    business = await session.get(Business, DEMO_BUSINESS_ID)
    if business is None:
        session.add(
            Business(
                id=DEMO_BUSINESS_ID,
                name="Acme Global Holdings",
                industry="Diversified Services",
                currency="INR",
            )
        )
        await session.commit()

    existing = (await session.execute(
        select(FinancialRecord).where(FinancialRecord.business_id == DEMO_BUSINESS_ID)
    )).scalars().first()
    if existing is not None:
        return

    for item in _DEMO_PERIODS:
        session.add(FinancialRecord(business_id=DEMO_BUSINESS_ID, source="demo", verified=False, **item))

    session.add(
        Budget(
            business_id=DEMO_BUSINESS_ID,
            period="2026-Q3",
            scope="category",
            category="Marketing",
            budgeted_amount=50000.0,
        )
    )
    session.add(
        ExpenseRecord(
            business_id=DEMO_BUSINESS_ID,
            date="2026-09-15",
            category="Marketing",
            description="Demo campaign spend",
            vendor="Demo Vendor",
            amount=65000.0,
            department="Marketing",
            source="demo",
        )
    )
    session.add(
        CashFlowRecord(
            business_id=DEMO_BUSINESS_ID,
            period="2026-Q3",
            opening_cash=58000.0,
            operating_inflow=310000.0,
            operating_outflow=283000.0,
            investing_inflow=2000.0,
            investing_outflow=12000.0,
            financing_inflow=0.0,
            financing_outflow=6000.0,
            closing_cash=62000.0,
            notes="Demo cash-flow period",
        )
    )
    session.add(
        CapitalStructureRecord(
            business_id=DEMO_BUSINESS_ID,
            period="2026-Q3",
            shareholders_equity=182000.0,
            total_debt=98000.0,
            short_term_debt=18000.0,
            long_term_debt=80000.0,
            total_assets=280000.0,
            ebit=92000.0,
            interest_expense=1900.0,
        )
    )
    await session.commit()
