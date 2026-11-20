from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.schemas import AlertItem


class FinancialRecordIn(BaseModel):
    period: str
    revenue: float = 0.0
    cogs: float = 0.0
    operating_expenses: float = 0.0
    net_income: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    period_start: str = ""
    period_end: str = ""
    cash: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    other_current_assets: float | None = None
    total_current_assets: float | None = None
    total_current_liabilities: float | None = None
    short_term_debt: float | None = None
    long_term_debt: float | None = None
    interest_expense: float | None = None
    ebit: float | None = None
    operating_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    opening_cash: float | None = None
    closing_cash: float | None = None
    source: str = "manual"
    source_document_id: str = ""
    notes: str = ""


class FinancialRecordOut(FinancialRecordIn):
    id: str
    business_id: str
    verified: bool
    created_at: str


class ContextEntry(BaseModel):
    category: str
    label: str
    value: str
    source: str


class FinancialContextOut(BaseModel):
    business_id: str
    generated_at: str
    entries: list[ContextEntry]
    prompt_context: str
    periods: list[str]
    source_counts: dict[str, int]


class MoneyTransactionIn(BaseModel):
    date: str
    amount: float
    category: str = ""
    description: str = ""
    vendor: str = ""
    department: str = ""
    reference: str = ""
    source: str = "manual"


class MoneyTransactionOut(MoneyTransactionIn):
    id: str
    business_id: str
    ai_categorized: bool = False
    created_at: str


class TransactionImportOut(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
    categories: dict[str, int]


class BudgetIn(BaseModel):
    period: str
    category: str = ""
    department: str = ""
    project: str = ""
    scope: str = "category"
    budgeted_amount: float = 0.0


class BudgetOut(BudgetIn):
    id: str
    business_id: str
    created_at: str


class VarianceOut(BaseModel):
    category: str
    budgeted: float
    actual: float
    variance_abs: float
    variance_pct: float
    severity: str
    favorable: bool
    explanation: str


class VarianceAnalysisOut(BaseModel):
    period: str
    items: list[VarianceOut]
    total_budgeted: float
    total_actual: float
    total_variance_pct: float
    narrative: str
    revenue_context: dict


class CashFlowIn(BaseModel):
    period: str
    opening_cash: float = 0.0
    operating_inflow: float = 0.0
    operating_outflow: float = 0.0
    investing_inflow: float = 0.0
    investing_outflow: float = 0.0
    financing_inflow: float = 0.0
    financing_outflow: float = 0.0
    notes: str = ""


class CashFlowOut(CashFlowIn):
    id: str
    business_id: str
    closing_cash: float
    net_cash_flow: float
    created_at: str


class CashFlowAnalysisOut(BaseModel):
    records: list[CashFlowOut]
    latest: CashFlowOut | None
    runway_months: float | None
    runway_note: str
    average_monthly_burn: float
    liquidity_note: str
    monthly: list[dict]


class CapitalStructureIn(BaseModel):
    period: str
    shareholders_equity: float = 0.0
    total_debt: float = 0.0
    short_term_debt: float = 0.0
    long_term_debt: float = 0.0
    total_assets: float = 0.0
    ebit: float | None = None
    interest_expense: float | None = None
    cost_of_equity_pct: float = 10.0
    cost_of_debt_pct: float = 6.0
    tax_rate_pct: float = 25.0


class CapitalStructureOut(CapitalStructureIn):
    id: str
    business_id: str
    created_at: str


class CapitalAnalysisOut(BaseModel):
    records: list[CapitalStructureOut]
    metrics: dict
    explanations: dict[str, str]
    recommendation: str


class WorkingCapitalOut(BaseModel):
    period: str
    working_capital: float
    current_ratio: float | None
    quick_ratio: float | None
    receivables: float
    payables: float
    inventory: float
    trend: list[dict]


class LoanIn(BaseModel):
    name: str = "Loan"
    principal: float
    annual_rate_pct: float
    tenure_months: int


class AmortizationRow(BaseModel):
    month: int
    opening_balance: float
    interest: float
    principal: float
    closing_balance: float


class LoanQuoteOut(BaseModel):
    monthly_emi: float
    total_interest: float
    total_repayment: float
    schedule: list[AmortizationRow]


class LoanOut(LoanIn):
    id: str
    business_id: str
    created_at: str


class ForecastIn(BaseModel):
    metric: str
    series: list[float]
    periods_ahead: int = 3
    method: str = "auto"
    store: bool = False


class ForecastOut(BaseModel):
    metric: str
    method: str
    history: list[dict]
    forecast: list[dict]
    assumptions: list[str]
    uncertainty: list[dict]


class ScenarioIn(BaseModel):
    name: str
    payload: dict
    result: dict


class ScenarioOut(ScenarioIn):
    id: str
    business_id: str
    created_at: str


class StockInfoOut(BaseModel):
    symbol: str
    name: str
    exchange: str
    currency: str
    source: str
    data_status: str
    as_of: str
    latest_price: float | None
    daily_change: float | None
    daily_change_pct: float | None
    volume: float | None
    trend: str


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class StockHistoryOut(BaseModel):
    symbol: str
    source: str
    data_status: str
    as_of: str
    points: list[PricePoint]


class IndicatorOut(BaseModel):
    indicator: str
    description: str
    values: list[dict]


class IndicatorsOut(BaseModel):
    symbol: str
    source: str
    data_status: str
    indicators: list[IndicatorOut]


class PredictionOut(BaseModel):
    id: str
    symbol: str
    model: str
    horizon_days: int
    predicted_price: float
    predicted_direction: str
    lower_bound: float | None
    upper_bound: float | None
    last_actual_price: float
    metrics: dict
    created_at: str
    target_date: str
    actual_price: float | None
    data_source: str


class PredictionRequest(BaseModel):
    symbol: str
    horizon_days: int = 1
    model: str = "linear_regression"
    store: bool = True


class EvaluationOut(BaseModel):
    symbol: str
    model: str
    horizon_days: int
    mae: float
    rmse: float
    directional_accuracy: float
    sample_size: int
    data_source: str
    created_at: str


class WatchlistIn(BaseModel):
    symbol: str
    threshold_pct: float = 3.0
    enabled: bool = True


class WatchlistOut(WatchlistIn):
    id: str
    business_id: str


class PortfolioIn(BaseModel):
    name: str
    initial_cash: float = 100000.0


class PortfolioOut(BaseModel):
    id: str
    business_id: str
    name: str
    initial_cash: float
    cash: float
    invested: float
    total_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    holdings: list[dict]
    created_at: str


class TradeIn(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    fee: float = 0.0


class TradeOut(BaseModel):
    id: str
    portfolio_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    amount: float
    fee: float
    realized_pnl: float
    executed_at: str


class FraudTransactionIn(BaseModel):
    transaction_id: str
    date: str = ""
    amount: float | None = None
    vendor: str = ""
    transaction_type: str = "payment"
    reference: str = ""


class FraudTransactionOut(BaseModel):
    id: str
    business_id: str
    transaction_id: str
    date: str
    amount: float | None
    vendor: str
    transaction_type: str
    reference: str
    source: str
    batch_id: str
    created_at: str


class FraudUploadOut(BaseModel):
    batch_id: str
    received: int
    valid: int
    invalid: int
    validation_errors: list[str]
    alerts_created: int
    summary: dict


class AlertOut(BaseModel):
    id: str
    transaction_id: str
    amount: float | None
    date: str
    vendor: str
    risk_level: str
    reason: str
    detection_method: str
    recommended_action: str
    status: str
    created_at: str


class ReviewIn(BaseModel):
    action: str
    note: str = ""
    reviewer: str = "owner"


class FraudSummaryOut(BaseModel):
    total_transactions: int
    suspicious_transactions: int
    high_risk_alerts: int
    duplicate_count: int
    risk_distribution: dict[str, int]
    status_distribution: dict[str, int]
    alerts: list[AlertOut]
    review_history: list[dict]


class WorkflowOut(BaseModel):
    id: str
    name: str
    workflow_type: str
    enabled: bool
    webhook_url: str
    schedule: str
    last_run_at: str
    last_status: str


class WorkflowIn(BaseModel):
    name: str
    workflow_type: str
    webhook_url: str = ""
    schedule: str = ""
    enabled: bool = True


class WorkflowUpdateIn(BaseModel):
    name: str | None = None
    webhook_url: str | None = None
    schedule: str | None = None
    enabled: bool | None = None


class WebhookEventIn(BaseModel):
    event_id: str = ""
    event_type: str = "notification"
    workflow: str = ""
    payload: dict = {}


class WebhookEventOut(BaseModel):
    event_id: str
    source: str
    event_type: str
    business_id: str
    status: str
    received_at: str


class ExecutionLogOut(BaseModel):
    id: str
    workflow: str
    event_id: str
    status: str
    message: str
    duration_ms: int
    created_at: str


class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    severity: str
    channel: str
    is_read: bool
    created_at: str


class AutomationStatusOut(BaseModel):
    configured: bool
    workflows: list[WorkflowOut]
    recent_events: list[WebhookEventOut]
    recent_logs: list[ExecutionLogOut]
    notifications: list[NotificationOut]


class ExtractedFieldOut(BaseModel):
    id: str
    document_id: str
    field_name: str
    field_value: str
    confidence: float
    verified: bool
    period: str


class FieldVerificationIn(BaseModel):
    verified: bool = True
    field_value: str | None = None


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str
    chunks: int
    fields: list[ExtractedFieldOut]


# ---------------------------------------------------------------------------
# Live benchmark market data (Twelve Data) + investment outlook
# ---------------------------------------------------------------------------


class MarketQuote(BaseModel):
    symbol: str
    name: str = ""
    exchange: str = ""
    currency: str = ""
    price: float | None = None
    change: float | None = None
    percent_change: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: int | None = None
    is_market_open: bool | None = None
    updated_at: str | None = None


class MarketOverview(BaseModel):
    quotes: list[MarketQuote]
    as_of: str
    source: str = "twelvedata"
    cached: bool = False


class MarketSearchResult(BaseModel):
    symbol: str
    name: str = ""
    exchange: str = ""
    currency: str = ""
    instrument_type: str = ""
    country: str = ""


class MarketPricePoint(BaseModel):
    datetime: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class MarketHistory(BaseModel):
    symbol: str
    interval: str = "1day"
    currency: str = ""
    exchange: str = ""
    points: list[MarketPricePoint]


class MarketUsage(BaseModel):
    current_usage: int | None = None
    plan_limit: int | None = None
    daily_usage: int | None = None
    plan_daily_limit: int | None = None
    plan_category: str = ""


class InvestmentOutlookRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=24)
    amount: float = Field(..., gt=0, description="Amount to invest, in the quote currency")
    horizon_months: int = Field(12, ge=1, le=60)
    cash_available: float | None = Field(None, ge=0)
    monthly_net_income: float | None = Field(None, ge=0)
    notify: bool = Field(
        False, description="Also raise an alert (and dispatch it to n8n when configured)"
    )


class InvestmentOutlookResponse(BaseModel):
    symbol: str
    investment: float
    horizon_months: int
    horizon_days: int

    annualized_return_pct: float
    annualized_volatility_pct: float
    sharpe_like: float | None = None

    expected_value: float
    expected_profit: float
    expected_profit_pct: float

    best_case_value: float
    best_case_profit: float
    worst_case_value: float
    worst_case_profit: float

    var_95_value: float
    var_95_loss: float
    probability_of_loss_pct: float
    max_drawdown_pct: float
    observations: int
    notes: list[str] = []

    as_of: str
    latest_close: float | None = None
    alert: AlertItem | None = None
