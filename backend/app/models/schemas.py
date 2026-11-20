from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: str


class MeResponse(BaseModel):
    user_id: str
    business_id: str
    role: str


# ---------------------------------------------------------------------------
# Budget Variance
# ---------------------------------------------------------------------------


class BudgetVarianceRequest(BaseModel):
    period: str = Field(..., examples=["2026-Q3"])
    budget: dict[str, float]
    actual: dict[str, float]
    revenue_categories: list[str] = Field(default_factory=list)
    watch_threshold_pct: float = 5.0
    breach_threshold_pct: float = 10.0


class LineItemVarianceOut(BaseModel):
    category: str
    budgeted: float
    actual: float
    variance_abs: float
    variance_pct: float
    severity: str
    favorable: bool


class BudgetVarianceResponse(BaseModel):
    period: str
    items: list[LineItemVarianceOut]
    total_budgeted: float
    total_actual: float
    total_variance_pct: float
    breaches: list[str]


# ---------------------------------------------------------------------------
# Financial Statement / Ratios
# ---------------------------------------------------------------------------


class BalanceSheetIn(BaseModel):
    cash: float
    accounts_receivable: float
    inventory: float
    other_current_assets: float
    total_current_assets: float
    total_assets: float
    total_current_liabilities: float
    total_liabilities: float
    total_equity: float


class IncomeStatementIn(BaseModel):
    revenue: float
    cogs: float
    operating_expenses: float
    net_income: float


class RatioOut(BaseModel):
    name: str
    value: float | None
    interpretation: str


class FinancialStatementRequest(BaseModel):
    balance_sheet: BalanceSheetIn
    income_statement: IncomeStatementIn


class FinancialStatementResponse(BaseModel):
    ratios: list[RatioOut]


# ---------------------------------------------------------------------------
# Capital Structure
# ---------------------------------------------------------------------------


class CapitalStructureRequest(BaseModel):
    market_value_equity: float
    market_value_debt: float
    cost_of_equity_pct: float
    cost_of_debt_pct: float
    tax_rate_pct: float


class CapitalStructureResponse(BaseModel):
    equity_weight: float
    debt_weight: float
    after_tax_cost_of_debt_pct: float
    wacc_pct: float
    leverage_ratio: float


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class RiskRequest(BaseModel):
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    net_margin_pct: float | None = None
    cash_runway_months: float | None = None
    revenue_mom_change_pct: float | None = None


class RiskFlagOut(BaseModel):
    code: str
    message: str
    level: str
    metric_value: float | None = None


class RiskResponse(BaseModel):
    overall_score: int
    overall_level: str
    flags: list[RiskFlagOut]


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------


class ForecastRequest(BaseModel):
    series: list[float]
    periods_ahead: int = 3


class ForecastPointOut(BaseModel):
    period_index: int
    value: float


class ForecastResponse(BaseModel):
    method: str
    slope: float
    r_squared: float
    history: list[ForecastPointOut]
    forecast: list[ForecastPointOut]


# ---------------------------------------------------------------------------
# What-If Simulator
# ---------------------------------------------------------------------------


class SimulationLeversIn(BaseModel):
    monthly_revenue_growth_pct: float = 0.0
    monthly_cost_growth_pct: float = 0.0
    one_time_cost_change: float = 0.0
    new_monthly_fixed_cost: float = 0.0
    price_change_pct: float = 0.0


class WhatIfRequest(BaseModel):
    starting_revenue: float
    starting_costs: float
    starting_cash: float
    levers: SimulationLeversIn = Field(default_factory=SimulationLeversIn)
    periods: int = 12


class SimulationPeriodOut(BaseModel):
    period_index: int
    revenue: float
    costs: float
    net_income: float
    cash_balance: float


class WhatIfResponse(BaseModel):
    periods: list[SimulationPeriodOut]
    ending_cash: float
    breakeven_period: int | None


# ---------------------------------------------------------------------------
# AI Advisor (LangGraph)
# ---------------------------------------------------------------------------


class AdvisorRequest(BaseModel):
    query: str
    extracted_params: dict = Field(default_factory=dict)


class AdvisorResponse(BaseModel):
    intent: str
    route: str
    is_valid: bool
    tool_result: dict
    citations: list[str]
    validation_notes: list[str]
    answer: str


# ---------------------------------------------------------------------------
# Documents / RAG
# ---------------------------------------------------------------------------


class DocumentUploadResponse(BaseModel):
    document_id: str
    source: str
    chunks_indexed: int


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    business_name: str
    period: str
    ratios: list[RatioOut] = Field(default_factory=list)
    risk: RiskResponse | None = None
    notes: str = ""


class ReportResponse(BaseModel):
    report_id: str
    title: str
    generated_sections: list[str]


# ---------------------------------------------------------------------------
# Alerts & n8n Automation
# ---------------------------------------------------------------------------


class AlertItem(BaseModel):
    id: str
    business_id: str
    title: str
    message: str
    severity: str = "watch"  # info | watch | critical | low
    source: str = "n8n_automation"  # n8n_automation | risk_engine | budget_engine
    timestamp: str
    read: bool = False


class AlertWebhookPayload(BaseModel):
    business_id: str = "demo-business-001"
    title: str
    message: str
    severity: str = "watch"
    source: str = "n8n_automation"


class TriggerAlertCheckResponse(BaseModel):
    status: str
    alerts_generated: int
    n8n_webhook_dispatched: bool
    alerts: list[AlertItem]

