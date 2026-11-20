from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenPayload, get_current_user
from app.db.extensions import (
    Budget,
    BudgetVarianceRecord,
    CapitalStructureRecord,
    CashFlowRecord,
    ExpenseRecord,
    ForecastRecord,
    IncomeRecord,
    LoanScenario,
    SavedScenario,
)
from app.db.models import FinancialRecord
from app.db.session import get_session
from app.db.util import as_dict
from app.engines.forecasting import forecast_series
from app.engines.loan import loan_quote
from app.engines.money_management import (
    analyze_budget_variance,
    analyze_capital_structure,
    analyze_cashflow,
    analyze_working_capital,
    categorize_transaction,
)
from app.models.schemas_ext import (
    BudgetIn,
    BudgetOut,
    CapitalAnalysisOut,
    CapitalStructureIn,
    CapitalStructureOut,
    CashFlowAnalysisOut,
    CashFlowIn,
    CashFlowOut,
    ForecastIn,
    ForecastOut,
    LoanIn,
    LoanOut,
    LoanQuoteOut,
    MoneyTransactionIn,
    MoneyTransactionOut,
    ScenarioIn,
    ScenarioOut,
    TransactionImportOut,
    VarianceAnalysisOut,
    WorkingCapitalOut,
)

router = APIRouter(prefix="/money", tags=["money-management"])


def _transaction_out(row: IncomeRecord | ExpenseRecord, kind: str) -> MoneyTransactionOut:
    data = as_dict(row)
    data["amount"] = float(data["amount"]) if kind == "income" else -abs(float(data["amount"]))
    data["ai_categorized"] = bool(data.get("ai_categorized", True))
    return MoneyTransactionOut(**data)


@router.post("/transactions", response_model=MoneyTransactionOut)
async def add_transaction(
    payload: MoneyTransactionIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MoneyTransactionOut:
    amount = float(payload.amount)
    category = payload.category.strip()
    ai_categorized = bool(category)
    if not category:
        category, confidence, ai_categorized = categorize_transaction(payload.vendor, payload.description, amount)
    else:
        confidence = 1.0
    values = {
        "business_id": user.business_id,
        "date": payload.date,
        "category": category,
        "description": payload.description,
        "vendor": payload.vendor,
        "department": payload.department,
        "reference": payload.reference,
        "source": payload.source,
    }
    if amount >= 0:
        row = IncomeRecord(**values, amount=amount)
    else:
        row = ExpenseRecord(**values, amount=abs(amount), ai_categorized=ai_categorized)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    result = _transaction_out(row, "income" if amount >= 0 else "expense")
    result.description = f"{result.description} [confidence {confidence:.2f}]" if not payload.category else result.description
    return result


@router.get("/transactions", response_model=list[MoneyTransactionOut])
async def list_transactions(
    kind: str = "all",
    limit: int = 200,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MoneyTransactionOut]:
    if kind not in ("all", "income", "expense"):
        raise HTTPException(status_code=422, detail="kind must be all, income or expense")
    output: list[MoneyTransactionOut] = []
    if kind in ("all", "income"):
        rows = (await session.execute(
            select(IncomeRecord).where(IncomeRecord.business_id == user.business_id).order_by(IncomeRecord.date.desc()).limit(limit)
        )).scalars().all()
        output.extend(_transaction_out(row, "income") for row in rows)
    if kind in ("all", "expense"):
        rows = (await session.execute(
            select(ExpenseRecord).where(ExpenseRecord.business_id == user.business_id).order_by(ExpenseRecord.date.desc()).limit(limit)
        )).scalars().all()
        output.extend(_transaction_out(row, "expense") for row in rows)
    return sorted(output, key=lambda item: item.date, reverse=True)[:limit]


@router.post("/transactions/import", response_model=TransactionImportOut)
async def import_transactions(
    file: UploadFile,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TransactionImportOut:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from error
    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = 0
    errors: list[str] = []
    categories: dict[str, int] = {}
    for index, row in enumerate(reader, start=2):
        try:
            date = (row.get("date") or row.get("Date") or "").strip()
            amount = float(row.get("amount") or row.get("Amount") or "0")
            vendor = (row.get("vendor") or row.get("Vendor") or "").strip()
            description = (row.get("description") or row.get("Description") or "").strip()
            category = (row.get("category") or row.get("Category") or "").strip()
            if not date or amount == 0:
                skipped += 1
                errors.append(f"Row {index}: missing date or zero amount")
                continue
            if not category:
                category, _, _ = categorize_transaction(vendor, description, amount)
            categories[category] = categories.get(category, 0) + 1
            values = {
                "business_id": user.business_id,
                "date": date,
                "category": category,
                "description": description,
                "vendor": vendor,
                "department": (row.get("department") or "").strip(),
                "reference": (row.get("reference") or "").strip(),
                "source": "csv_import",
            }
            if amount >= 0:
                session.add(IncomeRecord(**values, amount=amount))
            else:
                session.add(ExpenseRecord(**values, amount=abs(amount), ai_categorized=True))
            imported += 1
        except (ValueError, TypeError) as error:
            skipped += 1
            errors.append(f"Row {index}: {error}")
    await session.commit()
    return TransactionImportOut(imported=imported, skipped=skipped, errors=errors[:20], categories=categories)


@router.post("/budgets", response_model=BudgetOut)
async def add_budget(
    payload: BudgetIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BudgetOut:
    row = Budget(business_id=user.business_id, **payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return BudgetOut(**as_dict(row))


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets(
    period: str | None = None,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[BudgetOut]:
    query = select(Budget).where(Budget.business_id == user.business_id)
    if period:
        query = query.where(Budget.period == period)
    rows = (await session.execute(query.order_by(Budget.period, Budget.category))).scalars().all()
    return [BudgetOut(**as_dict(row)) for row in rows]


@router.get("/variance/{period}", response_model=VarianceAnalysisOut)
async def variance_analysis(
    period: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VarianceAnalysisOut:
    budgets = (await session.execute(
        select(Budget).where(Budget.business_id == user.business_id, Budget.period == period)
    )).scalars().all()
    expenses = (await session.execute(
        select(ExpenseRecord).where(ExpenseRecord.business_id == user.business_id)
    )).scalars().all()
    result = analyze_budget_variance([as_dict(row) for row in budgets], [as_dict(row) for row in expenses])

    for item in result["items"]:
        session.add(
            BudgetVarianceRecord(
                business_id=user.business_id,
                period=period,
                category=item["category"],
                budgeted=item["budgeted"],
                actual=item["actual"],
                variance_abs=item["variance_abs"],
                variance_pct=item["variance_pct"],
                severity=item["severity"],
                favorable=item["favorable"],
            )
        )
    records = (await session.execute(
        select(FinancialRecord).where(FinancialRecord.business_id == user.business_id, FinancialRecord.period == period)
    )).scalars().first()
    revenue = float(records.revenue) if records and records.revenue is not None else 0.0
    await session.commit()
    result["period"] = period
    result["revenue_context"] = {
        "revenue": round(revenue, 2),
        "spend_as_pct_of_revenue": round((result["total_actual"] / revenue) * 100, 2) if revenue else None,
    }
    return VarianceAnalysisOut(**result)


@router.post("/cashflow", response_model=CashFlowOut)
async def add_cashflow(
    payload: CashFlowIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CashFlowOut:
    values = payload.model_dump()
    inflow = sum(values.get(key, 0) for key in ("operating_inflow", "investing_inflow", "financing_inflow"))
    outflow = sum(values.get(key, 0) for key in ("operating_outflow", "investing_outflow", "financing_outflow"))
    row = CashFlowRecord(
        business_id=user.business_id,
        closing_cash=values["opening_cash"] + inflow - outflow,
        **values,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    data = as_dict(row)
    data["net_cash_flow"] = round(inflow - outflow, 2)
    return CashFlowOut(**data)


@router.get("/cashflow/analysis", response_model=CashFlowAnalysisOut)
async def cashflow_analysis(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CashFlowAnalysisOut:
    rows = (await session.execute(
        select(CashFlowRecord).where(CashFlowRecord.business_id == user.business_id)
    )).scalars().all()
    result = analyze_cashflow([as_dict(row) for row in rows])
    result["records"] = [CashFlowOut(**{**row, "created_at": row.get("created_at", "")}) for row in result["records"]]
    if result["latest"]:
        result["latest"] = CashFlowOut(**{**result["latest"], "created_at": result["latest"].get("created_at", "")})
    return CashFlowAnalysisOut(**result)


@router.post("/capital", response_model=CapitalAnalysisOut)
async def add_capital(
    payload: CapitalStructureIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapitalAnalysisOut:
    session.add(CapitalStructureRecord(business_id=user.business_id, **payload.model_dump()))
    await session.commit()
    return await capital_analysis(user, session)


@router.get("/capital/analysis", response_model=CapitalAnalysisOut)
async def capital_analysis(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapitalAnalysisOut:
    rows = (await session.execute(
        select(CapitalStructureRecord).where(CapitalStructureRecord.business_id == user.business_id)
    )).scalars().all()
    result = analyze_capital_structure([as_dict(row) for row in rows])
    result["records"] = [CapitalStructureOut(**row) for row in result["records"]]
    return CapitalAnalysisOut(**result)


@router.get("/working-capital", response_model=WorkingCapitalOut)
async def working_capital(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WorkingCapitalOut:
    rows = (await session.execute(
        select(FinancialRecord).where(FinancialRecord.business_id == user.business_id).order_by(FinancialRecord.period)
    )).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No financial records available for working capital analysis")
    trend = [
        {
            "period": row.period,
            "current_ratio": round(row.total_current_assets / row.total_current_liabilities, 4)
            if row.total_current_liabilities
            else None,
            "working_capital": round((row.total_current_assets or 0) - (row.total_current_liabilities or 0), 2),
        }
        for row in rows
    ]
    return WorkingCapitalOut(**analyze_working_capital(as_dict(rows[-1]), trend))


@router.post("/loans", response_model=LoanOut)
async def add_loan(
    payload: LoanIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanOut:
    row = LoanScenario(business_id=user.business_id, **payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return LoanOut(**as_dict(row))


@router.get("/loans", response_model=list[LoanOut])
async def list_loans(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LoanOut]:
    rows = (await session.execute(
        select(LoanScenario).where(LoanScenario.business_id == user.business_id)
    )).scalars().all()
    return [LoanOut(**as_dict(row)) for row in rows]


@router.post("/loans/quote", response_model=LoanQuoteOut)
async def quote_loan(payload: LoanIn, _user: TokenPayload = Depends(get_current_user)) -> LoanQuoteOut:
    try:
        return LoanQuoteOut(**loan_quote(payload.principal, payload.annual_rate_pct, payload.tenure_months))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/loans/{loan_id}/quote", response_model=LoanQuoteOut)
async def quote_saved_loan(
    loan_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanQuoteOut:
    row = await session.get(LoanScenario, loan_id)
    if row is None or row.business_id != user.business_id:
        raise HTTPException(status_code=404, detail="Loan scenario not found")
    return LoanQuoteOut(**loan_quote(row.principal, row.annual_rate_pct, row.tenure_months))


@router.post("/forecast", response_model=ForecastOut)
async def forecast(
    payload: ForecastIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ForecastOut:
    try:
        result = forecast_series(payload.metric, payload.series, payload.periods_ahead, payload.method)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if payload.store:
        session.add(
            ForecastRecord(
                business_id=user.business_id,
                metric=payload.metric,
                method=result["method"],
                horizon=payload.periods_ahead,
                points_json=json.dumps(result["forecast"]),
                assumptions_json=json.dumps(result["assumptions"]),
            )
        )
        await session.commit()
    return ForecastOut(**result)


@router.get("/forecasts", response_model=list[dict])
async def list_forecasts(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (await session.execute(
        select(ForecastRecord).where(ForecastRecord.business_id == user.business_id).order_by(ForecastRecord.created_at.desc())
    )).scalars().all()
    output = []
    for row in rows:
        data = as_dict(row)
        data["points"] = json.loads(row.points_json)
        data["assumptions"] = json.loads(row.assumptions_json)
        output.append(data)
    return output


@router.post("/scenarios", response_model=ScenarioOut)
async def save_scenario(
    payload: ScenarioIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScenarioOut:
    row = SavedScenario(
        business_id=user.business_id,
        name=payload.name,
        payload_json=json.dumps(payload.payload),
        result_json=json.dumps(payload.result),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    data = as_dict(row)
    data["payload"] = payload.payload
    data["result"] = payload.result
    return ScenarioOut(**data)


@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ScenarioOut]:
    rows = (await session.execute(
        select(SavedScenario).where(SavedScenario.business_id == user.business_id).order_by(SavedScenario.created_at.desc())
    )).scalars().all()
    output = []
    for row in rows:
        data = as_dict(row)
        data["payload"] = json.loads(row.payload_json)
        data["result"] = json.loads(row.result_json)
        output.append(ScenarioOut(**data))
    return output
