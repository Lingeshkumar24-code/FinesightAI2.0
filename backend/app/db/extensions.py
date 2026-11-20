from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="owner")
    password_hash: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_users_business_email", "business_id", "email", unique=True),)


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="calculated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_fin_metrics_scope", "business_id", "period", "name"),)


class IncomeRecord(Base):
    __tablename__ = "income_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, default="Other Income")
    description: Mapped[str] = mapped_column(String, default="")
    vendor: Mapped[str] = mapped_column(String, default="")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    department: Mapped[str] = mapped_column(String, default="")
    reference: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, default="Operations")
    description: Mapped[str] = mapped_column(String, default="")
    vendor: Mapped[str] = mapped_column(String, default="")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    department: Mapped[str] = mapped_column(String, default="")
    reference: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="manual")
    ai_categorized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, default="category")
    category: Mapped[str] = mapped_column(String, default="")
    department: Mapped[str] = mapped_column(String, default="")
    project: Mapped[str] = mapped_column(String, default="")
    budgeted_amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_budgets_scope", "business_id", "period", "scope", "category"),
    )


class BudgetVarianceRecord(Base):
    __tablename__ = "budget_variances"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    budgeted: Mapped[float] = mapped_column(Float, default=0.0)
    actual: Mapped[float] = mapped_column(Float, default=0.0)
    variance_abs: Mapped[float] = mapped_column(Float, default=0.0)
    variance_pct: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String, default="on_track")
    favorable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CashFlowRecord(Base):
    __tablename__ = "cash_flow_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String, nullable=False)
    opening_cash: Mapped[float] = mapped_column(Float, default=0.0)
    operating_inflow: Mapped[float] = mapped_column(Float, default=0.0)
    operating_outflow: Mapped[float] = mapped_column(Float, default=0.0)
    investing_inflow: Mapped[float] = mapped_column(Float, default=0.0)
    investing_outflow: Mapped[float] = mapped_column(Float, default=0.0)
    financing_inflow: Mapped[float] = mapped_column(Float, default=0.0)
    financing_outflow: Mapped[float] = mapped_column(Float, default=0.0)
    closing_cash: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_cashflow_business_period", "business_id", "period"),)


class CapitalStructureRecord(Base):
    __tablename__ = "capital_structures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period: Mapped[str] = mapped_column(String, nullable=False)
    shareholders_equity: Mapped[float] = mapped_column(Float, default=0.0)
    total_debt: Mapped[float] = mapped_column(Float, default=0.0)
    short_term_debt: Mapped[float] = mapped_column(Float, default=0.0)
    long_term_debt: Mapped[float] = mapped_column(Float, default=0.0)
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    ebit: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_expense: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_of_equity_pct: Mapped[float] = mapped_column(Float, default=10.0)
    cost_of_debt_pct: Mapped[float] = mapped_column(Float, default=6.0)
    tax_rate_pct: Mapped[float] = mapped_column(Float, default=25.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LoanScenario(Base):
    __tablename__ = "loan_scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, default="Loan")
    principal: Mapped[float] = mapped_column(Float, default=0.0)
    annual_rate_pct: Mapped[float] = mapped_column(Float, default=0.0)
    tenure_months: Mapped[int] = mapped_column(Integer, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, default="")
    horizon: Mapped[int] = mapped_column(Integer, default=0)
    points_json: Mapped[str] = mapped_column(Text, default="[]")
    assumptions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SavedScenario(Base):
    __tablename__ = "saved_scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StockInstrument(Base):
    __tablename__ = "stock_instruments"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    exchange: Mapped[str] = mapped_column(String, default="NSE")
    currency: Mapped[str] = mapped_column(String, default="INR")
    sector: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="yfinance")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trade_date: Mapped[str] = mapped_column(String, nullable=False)
    open: Mapped[float] = mapped_column(Float, default=0.0)
    high: Mapped[float] = mapped_column(Float, default=0.0)
    low: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_stock_price_symbol_date", "symbol", "trade_date", unique=True),)


class TechnicalIndicatorRow(Base):
    __tablename__ = "technical_indicators"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trade_date: Mapped[str] = mapped_column(String, nullable=False)
    indicator: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    params_json: Mapped[str] = mapped_column(Text, default="{}")

    __table_args__ = (
        Index("idx_tech_indicator_scope", "symbol", "trade_date", "indicator", unique=True),
    )


class PredictionRecord(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, default="linear_regression")
    horizon_days: Mapped[int] = mapped_column(Integer, default=1)
    predicted_price: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_direction: Mapped[str] = mapped_column(String, default="flat")
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_actual_price: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    target_date: Mapped[str] = mapped_column(String, default="")
    actual_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=1)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    rmse: Mapped[float] = mapped_column(Float, default=0.0)
    directional_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    backtest_json: Mapped[str] = mapped_column(Text, default="[]")
    data_source: Mapped[str] = mapped_column(String, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Float, default=3.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("idx_watchlist_business_symbol", "business_id", "symbol", unique=True),)


class VirtualPortfolio(Base):
    __tablename__ = "virtual_portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    initial_cash: Mapped[float] = mapped_column(Float, default=0.0)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("virtual_portfolios.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    average_cost: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("idx_holding_portfolio_symbol", "portfolio_id", "symbol", unique=True),)


class VirtualTransaction(Base):
    __tablename__ = "virtual_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("virtual_portfolios.id"), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    executed_at: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("virtual_portfolios.id"), nullable=False, index=True)
    snapshot_date: Mapped[str] = mapped_column(String, nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    invested: Mapped[float] = mapped_column(Float, default=0.0)
    total_value: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)


class FraudTransaction(Base):
    __tablename__ = "fraud_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[str] = mapped_column(String, default="")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vendor: Mapped[str] = mapped_column(String, default="")
    transaction_type: Mapped[str] = mapped_column(String, default="payment")
    reference: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="upload")
    batch_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_fraud_tx_business_external", "business_id", "transaction_id"),
    )


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    date: Mapped[str] = mapped_column(String, default="")
    vendor: Mapped[str] = mapped_column(String, default="")
    risk_level: Mapped[str] = mapped_column(String, default="low")
    reason: Mapped[str] = mapped_column(Text, default="")
    detection_method: Mapped[str] = mapped_column(String, default="rule")
    recommended_action: Mapped[str] = mapped_column(String, default="Verify with the vendor and reviewer")
    status: Mapped[str] = mapped_column(String, default="open")
    batch_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_fraud_alert_business_status", "business_id", "status"),
    )


class AlertReview(Base):
    __tablename__ = "alert_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    alert_id: Mapped[str] = mapped_column(ForeignKey("fraud_alerts.id"), nullable=False, index=True)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(String, default="")
    action: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WorkflowConfig(Base):
    __tablename__ = "workflow_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[str] = mapped_column(String, default="")
    schedule: Mapped[str] = mapped_column(String, default="")
    last_run_at: Mapped[str] = mapped_column(String, default="")
    last_status: Mapped[str] = mapped_column(String, default="never_run")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, default="n8n")
    event_type: Mapped[str] = mapped_column(String, default="")
    business_id: Mapped[str] = mapped_column(String, default="", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String, default="received")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, default="", index=True)
    workflow: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="success")
    message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String, default="info")
    channel: Mapped[str] = mapped_column(String, default="in_app")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIInteraction(Base):
    __tablename__ = "ai_interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String, default="")
    query: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    intent: Mapped[str] = mapped_column(String, default="")
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    field_value: Mapped[str] = mapped_column(String, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    period: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
