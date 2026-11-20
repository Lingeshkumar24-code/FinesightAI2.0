from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenPayload, get_current_user
from app.db.extensions import CashFlowRecord as CashFlowRow
from app.db.models import FinancialRecord
from app.db.session import get_session
from app.db.util import as_dict
from app.engines.financial_statement import BalanceSheet, FinancialStatementEngine, IncomeStatement
from app.engines.risk_detection import RiskDetectionEngine, RiskInputs
from app.models.schemas_ext import (
    FinancialContextOut,
    FinancialRecordIn,
    FinancialRecordOut,
)
from app.services.financial_context import build_context

router = APIRouter(prefix="/financials", tags=["financial-records"])


def _to_out(row: FinancialRecord) -> FinancialRecordOut:
    return FinancialRecordOut(**as_dict(row))


@router.get("/records", response_model=list[FinancialRecordOut])
async def list_records(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FinancialRecordOut]:
    rows = (await session.execute(
        select(FinancialRecord)
        .where(FinancialRecord.business_id == user.business_id)
        .order_by(FinancialRecord.period.asc())
    )).scalars().all()
    return [_to_out(row) for row in rows]


@router.post("/records", response_model=FinancialRecordOut)
async def upsert_record(
    payload: FinancialRecordIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialRecordOut:
    row = (await session.execute(
        select(FinancialRecord).where(
            FinancialRecord.business_id == user.business_id,
            FinancialRecord.period == payload.period,
        )
    )).scalars().first()
    data = payload.model_dump()
    if row is None:
        row = FinancialRecord(business_id=user.business_id, **data)
        session.add(row)
    else:
        for key, value in data.items():
            setattr(row, key, value)
        row.verified = False
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.post("/records/{record_id}/verify", response_model=FinancialRecordOut)
async def verify_record(
    record_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialRecordOut:
    row = await session.get(FinancialRecord, record_id)
    if row is None or row.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    row.verified = True
    row.source = "user_verified"
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.get(FinancialRecord, record_id)
    if row is None or row.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    await session.delete(row)
    await session.commit()
    return {"deleted": record_id}


@router.get("/context", response_model=FinancialContextOut)
async def financial_context(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialContextOut:
    return await build_context(session, user.business_id)


@router.get("/dashboard")
async def dashboard_summary(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (await session.execute(
        select(FinancialRecord)
        .where(FinancialRecord.business_id == user.business_id)
        .order_by(FinancialRecord.period.asc())
    )).scalars().all()
    if not rows:
        return {"available": False, "message": "No financial records submitted yet.", "periods": []}

    latest = rows[-1]
    cash = float(latest.cash or 0.0)
    current_assets = float(latest.total_current_assets or 0.0)
    current_liabilities = float(latest.total_current_liabilities or 0.0)
    cash_series = [float(r.closing_cash or r.cash or 0.0) for r in rows]
    for i in range(1, 7):
        if len(cash_series) > 1:
            avg_delta = (cash_series[-1] - cash_series[-2]) / 1.0
            cash_series.append(round(cash_series[-1] + avg_delta, 2))
        else:
            cash_series.append(cash_series[-1])

    bs = BalanceSheet(
        cash=cash,
        accounts_receivable=float(latest.accounts_receivable or 0.0),
        inventory=float(latest.inventory or 0.0),
        other_current_assets=float(latest.other_current_assets or 0.0),
        total_current_assets=current_assets,
        total_assets=float(latest.total_assets),
        total_current_liabilities=current_liabilities,
        total_liabilities=float(latest.total_liabilities),
        total_equity=float(latest.total_equity),
    )
    inc = IncomeStatement(
        revenue=float(latest.revenue),
        cogs=float(latest.cogs),
        operating_expenses=float(latest.operating_expenses),
        net_income=float(latest.net_income),
    )
    ratios = FinancialStatementEngine().compute(bs, inc)
    by_name = {r.name: r.value for r in ratios}

    burn = None
    if len(cash_series) > 1:
        recent = cash_series[-6:-1] if len(cash_series) >= 6 else cash_series[:-1]
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        if deltas:
            average_delta = sum(deltas) / len(deltas)
            if average_delta < 0:
                burn = abs(average_delta)
    runway = (cash / burn) if burn and burn > 0 else None

    risk = RiskDetectionEngine().evaluate(
        RiskInputs(
            current_ratio=by_name.get("current_ratio"),
            debt_to_equity=by_name.get("debt_to_equity"),
            net_margin_pct=by_name.get("net_margin_pct"),
            cash_runway_months=runway,
        )
    )

    cash_rows = (await session.execute(
        select(CashFlowRow)
        .where(CashFlowRow.business_id == user.business_id)
        .order_by(CashFlowRow.created_at.asc())
    )).scalars().all()

    return {
        "available": True,
        "source": latest.source,
        "verified": latest.verified,
        "data_label": "DEMO DATA" if latest.source == "demo" else ("VERIFIED" if latest.verified else "SUBMITTED"),
        "period": latest.period,
        "periods": [r.period for r in rows],
        "records": [_to_out(r).model_dump() for r in rows],
        "ratios": [r.__dict__ for r in ratios],
        "risk": {
            "overall_score": risk.overall_score,
            "overall_level": risk.overall_level.value,
            "flags": [f.__dict__ | {"level": f.level.value} for f in risk.flags],
        },
        "cash_series": cash_series,
        "cash_runway_months": runway,
        "cashflow_records": [as_dict(r) for r in cash_rows],
        "profit_margin_pct": by_name.get("net_margin_pct"),
    }
