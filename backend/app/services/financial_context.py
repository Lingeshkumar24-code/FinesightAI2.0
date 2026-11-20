from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.extensions import (
    AIInteraction,
    BudgetVarianceRecord,
    CapitalStructureRecord,
    CashFlowRecord,
    ExpenseRecord,
    ExtractedField,
    ForecastRecord,
    FraudAlert,
    IncomeRecord,
    PortfolioHolding,
    PredictionRecord,
    VirtualPortfolio,
)
from app.db.models import FinancialRecord
from app.engines.financial_statement import BalanceSheet, FinancialStatementEngine, IncomeStatement
from app.models.schemas_ext import ContextEntry, FinancialContextOut

_CATEGORIES = ("verified", "calculated", "historical", "forecast", "prediction", "recommendation")


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


async def _latest(session: AsyncSession, model, business_id: str):
    result = await session.execute(
        select(model).where(model.business_id == business_id).order_by(model.created_at.desc()).limit(1)
    )
    return result.scalars().first()


async def build_context(session: AsyncSession, business_id: str) -> FinancialContextOut:
    entries: list[ContextEntry] = []

    def add(category: str, label: str, value, source: str, suffix: str = "") -> None:
        entries.append(ContextEntry(category=category, label=label, value=_fmt(value, suffix), source=source))

    records_result = await session.execute(
        select(FinancialRecord)
        .where(FinancialRecord.business_id == business_id)
        .order_by(FinancialRecord.created_at.asc())
    )
    records = list(records_result.scalars().all())
    periods = [r.period for r in records]
    latest = records[-1] if records else None

    if latest is not None:
        source_label = (
            f"verified uploaded document {latest.source_document_id}"
            if latest.verified and latest.source_document_id
            else f"{latest.source} financial record"
        )
        verified_category = "verified" if latest.verified else "historical"
        add(verified_category, f"Revenue ({latest.period})", latest.revenue, source_label)
        add(verified_category, f"Net income ({latest.period})", latest.net_income, source_label)
        add(verified_category, f"Total assets ({latest.period})", latest.total_assets, source_label)
        add(verified_category, f"Total liabilities ({latest.period})", latest.total_liabilities, source_label)

        cash = _num(latest.cash) or 0.0
        receivables = _num(latest.accounts_receivable) or 0.0
        inventory = _num(latest.inventory) or 0.0
        other_ca = _num(latest.other_current_assets) or 0.0
        current_assets = _num(latest.total_current_assets)
        if current_assets is None:
            current_assets = cash + receivables + inventory + other_ca
        current_liabilities = _num(latest.total_current_liabilities) or 0.0

        bs = BalanceSheet(
            cash=cash,
            accounts_receivable=receivables,
            inventory=inventory,
            other_current_assets=other_ca,
            total_current_assets=current_assets,
            total_assets=latest.total_assets,
            total_current_liabilities=current_liabilities,
            total_liabilities=latest.total_liabilities,
            total_equity=latest.total_equity,
        )
        inc = IncomeStatement(
            revenue=latest.revenue,
            cogs=latest.cogs,
            operating_expenses=latest.operating_expenses,
            net_income=latest.net_income,
        )
        for ratio in FinancialStatementEngine().compute(bs, inc):
            add("calculated", ratio.name, ratio.value, "deterministic ratio engine")

    expense_rows = (await session.execute(
        select(ExpenseRecord).where(ExpenseRecord.business_id == business_id)
    )).scalars().all()
    income_rows = (await session.execute(
        select(IncomeRecord).where(IncomeRecord.business_id == business_id)
    )).scalars().all()
    if expense_rows or income_rows:
        add("historical", "Recorded expenses", sum(float(e.amount) for e in expense_rows), "money management records")
        add("historical", "Recorded income", sum(float(i.amount) for i in income_rows), "money management records")
        by_department: dict[str, float] = {}
        for expense in expense_rows:
            key = expense.department or "Unassigned"
            by_department[key] = by_department.get(key, 0.0) + float(expense.amount)
        for department, amount in sorted(by_department.items(), key=lambda item: -item[1])[:5]:
            add("historical", f"Spend · {department}", amount, "money management records")

    variance = await _latest(session, BudgetVarianceRecord, business_id)
    if variance is not None:
        add("calculated", f"Budget variance · {variance.category}", variance.variance_abs, "budget variance engine")
        add("calculated", "Budget variance %", variance.variance_pct, "budget variance engine", "%")

    cash_flow = await _latest(session, CashFlowRecord, business_id)
    if cash_flow is not None:
        add("historical", f"Closing cash ({cash_flow.period})", cash_flow.closing_cash, "cash flow records")
        add("calculated", "Net cash flow", cash_flow.closing_cash - cash_flow.opening_cash, "cash flow engine")

    capital = await _latest(session, CapitalStructureRecord, business_id)
    if capital is not None:
        equity = float(capital.shareholders_equity or 0.0)
        debt = float(capital.total_debt or 0.0)
        add("calculated", "Debt to equity", (debt / equity) if equity else None, "capital structure engine")
        add("calculated", "Debt to assets", (debt / float(capital.total_assets)) if capital.total_assets else None, "capital structure engine")

    forecast = await _latest(session, ForecastRecord, business_id)
    if forecast is not None:
        add("forecast", f"Forecast · {forecast.metric}", forecast.method, f"statistical forecast ({forecast.created_at.isoformat()})")

    prediction = await _latest(session, PredictionRecord, business_id)
    if prediction is not None:
        add(
            "prediction",
            f"Stock prediction · {prediction.symbol}",
            prediction.predicted_price,
            f"{prediction.model} ({prediction.created_at.isoformat()}), educational estimate",
        )

    open_alerts = (await session.execute(
        select(FraudAlert).where(FraudAlert.business_id == business_id, FraudAlert.status == "open")
    )).scalars().all()
    if open_alerts:
        add("recommendation", "Transactions requiring review", len(open_alerts), "fraud detection engine")

    portfolios = (await session.execute(
        select(VirtualPortfolio).where(VirtualPortfolio.business_id == business_id)
    )).scalars().all()
    for portfolio in portfolios:
        holdings = (await session.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)
        )).scalars().all()
        invested = sum(float(h.quantity) * float(h.average_cost) for h in holdings)
        add("historical", f"Paper portfolio · {portfolio.name}", invested, "virtual portfolio (no real money)")

    verified_fields = (await session.execute(
        select(ExtractedField).where(ExtractedField.business_id == business_id, ExtractedField.verified.is_(True))
    )).scalars().all()
    if verified_fields:
        add("verified", "Verified document fields", len(verified_fields), "user-reviewed document extraction")

    source_counts: dict[str, int] = {}
    for entry in entries:
        source_counts[entry.category] = source_counts.get(entry.category, 0) + 1

    lines = [
        "FINANCIAL CONTEXT (authoritative values only; labels indicate provenance)",
        f"Business: {business_id}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for category in _CATEGORIES:
        category_entries = [e for e in entries if e.category == category]
        if not category_entries:
            continue
        lines.append(f"[{category.upper()}]")
        for entry in category_entries:
            lines.append(f"- {entry.label}: {entry.value} (source: {entry.source})")
        lines.append("")
    lines.append(
        "Rules: use only these values. Never invent figures. Distinguish historical results, "
        "calculated metrics, forecasts, predictions and recommendations in the answer."
    )

    return FinancialContextOut(
        business_id=business_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
        prompt_context="\n".join(lines),
        periods=periods,
        source_counts=source_counts,
    )


async def log_interaction(
    session: AsyncSession,
    business_id: str,
    query: str,
    answer: str,
    intent: str,
    sources: list[str],
) -> None:
    session.add(
        AIInteraction(
            business_id=business_id,
            query=query,
            answer=answer,
            intent=intent,
            sources_json=json.dumps(sources),
        )
    )
    await session.commit()
