from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import TokenPayload, get_current_user
from app.engines.budget_variance import BudgetVarianceEngine
from app.engines.capital_structure import CapitalStructureEngine, CapitalStructureInput
from app.engines.financial_statement import BalanceSheet, FinancialStatementEngine, IncomeStatement
from app.engines.forecasting import ForecastingEngine
from app.engines.risk_detection import RiskDetectionEngine, RiskInputs
from app.models.schemas import (
    BudgetVarianceRequest,
    BudgetVarianceResponse,
    CapitalStructureRequest,
    CapitalStructureResponse,
    FinancialStatementRequest,
    FinancialStatementResponse,
    ForecastRequest,
    ForecastResponse,
    LineItemVarianceOut,
    RatioOut,
    RiskFlagOut,
    RiskRequest,
    RiskResponse,
)

router = APIRouter(prefix="/financials", tags=["financials"])


@router.post("/budget-variance", response_model=BudgetVarianceResponse)
def budget_variance(
    payload: BudgetVarianceRequest, _user: TokenPayload = Depends(get_current_user)
) -> BudgetVarianceResponse:
    engine = BudgetVarianceEngine(
        watch_threshold_pct=payload.watch_threshold_pct,
        breach_threshold_pct=payload.breach_threshold_pct,
    )
    report = engine.evaluate(
        period=payload.period,
        budget=payload.budget,
        actual=payload.actual,
        revenue_categories=set(payload.revenue_categories),
    )
    return BudgetVarianceResponse(
        period=report.period,
        items=[
            LineItemVarianceOut(**{**i.__dict__, "severity": i.severity.value})
            for i in report.items
        ],
        total_budgeted=report.total_budgeted,
        total_actual=report.total_actual,
        total_variance_pct=report.total_variance_pct,
        breaches=[b.category for b in report.breaches()],
    )


@router.post("/ratios", response_model=FinancialStatementResponse)
def financial_ratios(
    payload: FinancialStatementRequest, _user: TokenPayload = Depends(get_current_user)
) -> FinancialStatementResponse:
    engine = FinancialStatementEngine()
    bs = BalanceSheet(**payload.balance_sheet.model_dump())
    inc = IncomeStatement(**payload.income_statement.model_dump())
    ratios = engine.compute(bs, inc)
    return FinancialStatementResponse(ratios=[RatioOut(**r.__dict__) for r in ratios])


@router.post("/capital-structure", response_model=CapitalStructureResponse)
def capital_structure(
    payload: CapitalStructureRequest, _user: TokenPayload = Depends(get_current_user)
) -> CapitalStructureResponse:
    engine = CapitalStructureEngine()
    try:
        result = engine.compute(CapitalStructureInput(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return CapitalStructureResponse(**result.__dict__)


@router.post("/risk", response_model=RiskResponse)
def risk(payload: RiskRequest, _user: TokenPayload = Depends(get_current_user)) -> RiskResponse:
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs(**payload.model_dump()))
    return RiskResponse(
        overall_score=report.overall_score,
        overall_level=report.overall_level.value,
        flags=[RiskFlagOut(**{**f.__dict__, "level": f.level.value}) for f in report.flags],
    )


@router.post("/forecast", response_model=ForecastResponse)
def forecast(
    payload: ForecastRequest, _user: TokenPayload = Depends(get_current_user)
) -> ForecastResponse:
    engine = ForecastingEngine()
    try:
        result = engine.forecast_linear(payload.series, periods_ahead=payload.periods_ahead)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ForecastResponse(
        method=result.method,
        slope=result.slope,
        r_squared=result.r_squared,
        history=[h.__dict__ for h in result.history],
        forecast=[f.__dict__ for f in result.forecast],
    )
