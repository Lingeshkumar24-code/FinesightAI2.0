-- FinSight AI — Supabase Postgres schema
-- Mirrors backend/app/db/models.py and backend/app/db/extensions.py exactly.
-- If you change one, change the other.
--
-- Run via the Supabase SQL editor, or:
--   supabase db execute --file infra/supabase/schema.sql
--
-- Requires the pgvector extension (enabled by default on Supabase).

create extension if not exists vector;
create extension if not exists "uuid-ossp";

-- =====================================================================
-- CORE TENANT
-- =====================================================================

-- Businesses: tenant root — every other record hangs off this via
-- business_id. One row per company / SME using the product.
create table if not exists businesses (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    industry text default '',
    currency text default 'INR',
    -- References Supabase's built-in `auth.users` table. Left as a plain
    -- uuid (no FK constraint) so this schema also runs unmodified against
    -- vanilla Postgres in local/docker-compose dev, where auth.users
    -- doesn't exist. In Supabase, optionally tighten this with:
    --   alter table businesses
    --     add constraint businesses_owner_fk
    --     foreign key (owner_user_id) references auth.users (id) on delete set null;
    owner_user_id uuid,
    created_at timestamptz not null default now()
);

-- =====================================================================
-- USERS / AUTH
-- =====================================================================

-- Users: employees / owners of a business. Passwords are hashed server-side;
-- in production, replace with Supabase Auth and store only the user's
-- auth.users id here.
create table if not exists users (
    id text primary key,
    business_id text not null,
    email text not null,
    full_name text default '',
    role text default 'owner',
    password_hash text default '',
    is_active boolean default true,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_users_business_email on users (business_id, email);

-- =====================================================================
-- DOCUMENT MANAGEMENT & RAG
-- =====================================================================

-- Documents: uploaded financial files (Excel, CSV, PDF, TXT).
-- Supabase Storage holds the blob; this table holds metadata and
-- processing status so the UI can show progress.
create table if not exists documents (
    id uuid primary key default uuid_generate_v4(),
    business_id uuid not null references businesses (id) on delete cascade,
    filename text not null,
    storage_path text default '',
    status text not null default 'uploaded' check (status in ('uploaded', 'processed', 'failed')),
    created_at timestamptz not null default now()
);

create index if not exists idx_documents_business_id on documents (business_id);

-- Document chunks + embeddings: RAG index. 1536 dims fits
-- OpenAI text-embedding-3-small; adjust to match whichever embedding
-- model you actually call during ingestion.
create table if not exists document_chunks (
    id uuid primary key default uuid_generate_v4(),
    document_id uuid not null references documents (id) on delete cascade,
    chunk_index integer not null default 0,
    text text not null,
    source_location text default '',
    embedding vector(1536),
    created_at timestamptz not null default now()
);

create index if not exists idx_document_chunks_document_id on document_chunks (document_id);

-- IVFFlat index for approximate nearest-neighbor search. `lists` should
-- scale roughly with sqrt(row_count); 100 is a reasonable starting
-- point for an early-stage deployment.
create index if not exists idx_document_chunks_embedding
    on document_chunks using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- Extracted fields: structured key-value pairs pulled from uploaded docs
-- by the extraction pipeline (e.g. "revenue" -> "1200000", confidence 0.95).
create table if not exists extracted_fields (
    id text primary key,
    business_id text not null,
    document_id text not null,
    field_name text not null,
    field_value text default '',
    confidence real default 0.0,
    verified boolean default false,
    period text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_extracted_fields_business on extracted_fields (business_id);
create index if not exists idx_extracted_fields_document on extracted_fields (document_id);

-- =====================================================================
-- FINANCIAL RECORDS
-- =====================================================================

-- Financial records: one row per submitted / extracted reporting period.
-- Stores top-level P&L and balance-sheet numbers from which ratios are computed.
create table if not exists financial_records (
    id uuid primary key default uuid_generate_v4(),
    business_id uuid not null references businesses (id) on delete cascade,
    period text not null,
    revenue numeric not null default 0,
    cogs numeric not null default 0,
    operating_expenses numeric not null default 0,
    net_income numeric not null default 0,
    total_assets numeric not null default 0,
    total_liabilities numeric not null default 0,
    total_equity numeric not null default 0,
    period_start text default '',
    period_end text default '',
    cash numeric,
    accounts_receivable numeric,
    inventory numeric,
    other_current_assets numeric,
    total_current_assets numeric,
    total_current_liabilities numeric,
    short_term_debt numeric,
    long_term_debt numeric,
    interest_expense numeric,
    ebit numeric,
    operating_cash_flow numeric,
    investing_cash_flow numeric,
    financing_cash_flow numeric,
    opening_cash numeric,
    closing_cash numeric,
    source text default 'manual',
    source_document_id text default '',
    verified boolean default false,
    notes text default '',
    created_at timestamptz not null default now(),
    unique (business_id, period)
);

create index if not exists idx_financial_records_business_id on financial_records (business_id);

-- Financial metrics: computed KPIs (gross margin %, current ratio, ROE …)
-- stored after each analysis run so the dashboard can load them without
-- recalculating from scratch.
create table if not exists financial_metrics (
    id text primary key,
    business_id text not null,
    period text not null,
    name text not null,
    value real,
    unit text default '',
    source text default 'calculated',
    created_at timestamptz not null default now()
);

create index if not exists idx_fin_metrics_scope on financial_metrics (business_id, period, name);

-- Income records: individual revenue line items (invoices, subscriptions, etc.)
-- uploaded from Excel / CSV or entered manually.
create table if not exists income_records (
    id text primary key,
    business_id text not null,
    date text not null,
    category text default 'Other Income',
    description text default '',
    vendor text default '',
    amount real default 0.0,
    department text default '',
    reference text default '',
    source text default 'manual',
    created_at timestamptz not null default now()
);

create index if not exists idx_income_records_business on income_records (business_id);

-- Expense records: individual cost line items. ai_categorized = true means
-- the category was assigned by the LLM rather than the user.
create table if not exists expense_records (
    id text primary key,
    business_id text not null,
    date text not null,
    category text default 'Operations',
    description text default '',
    vendor text default '',
    amount real default 0.0,
    department text default '',
    reference text default '',
    source text default 'manual',
    ai_categorized boolean default false,
    created_at timestamptz not null default now()
);

create index if not exists idx_expense_records_business on expense_records (business_id);

-- =====================================================================
-- BUDGETING
-- =====================================================================

-- Budgets: planned spend targets per category / department / project within
-- a reporting period. scope distinguishes category-level vs dept-level budgets.
create table if not exists budgets (
    id text primary key,
    business_id text not null,
    period text not null,
    scope text default 'category',
    category text default '',
    department text default '',
    project text default '',
    budgeted_amount real default 0.0,
    created_at timestamptz not null default now()
);

create index if not exists idx_budgets_scope on budgets (business_id, period, scope, category);

-- Budget variances: computed diff between budgeted and actual spend.
-- Severity: on_track | watch | breach. Favorable = actual < budget for expenses.
create table if not exists budget_variances (
    id text primary key,
    business_id text not null,
    period text not null,
    category text not null,
    budgeted real default 0.0,
    actual real default 0.0,
    variance_abs real default 0.0,
    variance_pct real default 0.0,
    severity text default 'on_track',
    favorable boolean default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_budget_variances_business on budget_variances (business_id);

-- =====================================================================
-- CASH FLOW & CAPITAL
-- =====================================================================

-- Cash flow records: monthly operating / investing / financing cash flows.
-- Supports runway calculation and cash-flow forecasting.
create table if not exists cash_flow_records (
    id text primary key,
    business_id text not null,
    period text not null,
    opening_cash real default 0.0,
    operating_inflow real default 0.0,
    operating_outflow real default 0.0,
    investing_inflow real default 0.0,
    investing_outflow real default 0.0,
    financing_inflow real default 0.0,
    financing_outflow real default 0.0,
    closing_cash real default 0.0,
    notes text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_cashflow_business_period on cash_flow_records (business_id, period);

-- Capital structures: debt/equity snapshot used for WACC computation.
create table if not exists capital_structures (
    id text primary key,
    business_id text not null,
    period text not null,
    shareholders_equity real default 0.0,
    total_debt real default 0.0,
    short_term_debt real default 0.0,
    long_term_debt real default 0.0,
    total_assets real default 0.0,
    ebit real,
    interest_expense real,
    cost_of_equity_pct real default 10.0,
    cost_of_debt_pct real default 6.0,
    tax_rate_pct real default 25.0,
    created_at timestamptz not null default now()
);

create index if not exists idx_capital_structures_business on capital_structures (business_id);

-- Loan scenarios: saved EMI / amortization configurations for the loan engine.
create table if not exists loan_scenarios (
    id text primary key,
    business_id text not null,
    name text default 'Loan',
    principal real default 0.0,
    annual_rate_pct real default 0.0,
    tenure_months integer default 12,
    created_at timestamptz not null default now()
);

create index if not exists idx_loan_scenarios_business on loan_scenarios (business_id);

-- =====================================================================
-- FORECASTING & SCENARIOS
-- =====================================================================

-- Forecasts: saved linear / ML forecast runs. points_json holds the
-- per-period predictions as a JSON array.
create table if not exists forecasts (
    id text primary key,
    business_id text not null,
    metric text not null,
    method text default '',
    horizon integer default 0,
    points_json text default '[]',
    assumptions_json text default '[]',
    created_at timestamptz not null default now()
);

create index if not exists idx_forecasts_business on forecasts (business_id);

-- Saved scenarios: what-if simulation configs and results persisted for
-- later comparison (e.g. "hire 5 engineers" vs "raise prices 10%").
create table if not exists saved_scenarios (
    id text primary key,
    business_id text not null,
    name text not null,
    payload_json text default '{}',
    result_json text default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_saved_scenarios_business on saved_scenarios (business_id);

-- =====================================================================
-- MARKET INTELLIGENCE
-- =====================================================================

-- Stock instruments: master list of equity tickers (NSE, BSE, global).
create table if not exists stock_instruments (
    symbol text primary key,
    name text default '',
    exchange text default 'NSE',
    currency text default 'INR',
    sector text default '',
    source text default 'yfinance',
    updated_at timestamptz not null default now()
);

-- Stock prices: daily OHLCV bars for tracked instruments.
create table if not exists stock_prices (
    id text primary key,
    symbol text not null,
    trade_date text not null,
    open real default 0.0,
    high real default 0.0,
    low real default 0.0,
    close real default 0.0,
    volume real default 0.0,
    source text default 'yfinance',
    created_at timestamptz not null default now()
);

create unique index if not exists idx_stock_price_symbol_date on stock_prices (symbol, trade_date);
create index if not exists idx_stock_prices_symbol on stock_prices (symbol);

-- Technical indicators: RSI, MACD, Bollinger Bands, etc., computed on demand
-- and cached here to avoid recomputation.
create table if not exists technical_indicators (
    id text primary key,
    symbol text not null,
    trade_date text not null,
    indicator text not null,
    value real,
    params_json text default '{}'
);

create unique index if not exists idx_tech_indicator_scope on technical_indicators (symbol, trade_date, indicator);
create index if not exists idx_tech_indicators_symbol on technical_indicators (symbol);

-- Predictions: ML model price forecasts (linear regression, etc.) with
-- confidence intervals so the UI can show bull / bear bands.
create table if not exists predictions (
    id text primary key,
    business_id text not null,
    symbol text not null,
    model text default 'linear_regression',
    horizon_days integer default 1,
    predicted_price real default 0.0,
    predicted_direction text default 'flat',
    lower_bound real,
    upper_bound real,
    last_actual_price real default 0.0,
    metrics_json text default '{}',
    target_date text default '',
    actual_price real,
    data_source text default 'yfinance',
    created_at timestamptz not null default now()
);

create index if not exists idx_predictions_business on predictions (business_id);

-- Model evaluations: back-test accuracy metrics (MAE, RMSE, directional
-- accuracy) stored after each training run for model selection.
create table if not exists model_evaluations (
    id text primary key,
    symbol text not null,
    model text not null,
    horizon_days integer default 1,
    mae real default 0.0,
    rmse real default 0.0,
    directional_accuracy real default 0.0,
    sample_size integer default 0,
    backtest_json text default '[]',
    data_source text default 'yfinance',
    created_at timestamptz not null default now()
);

create index if not exists idx_model_evaluations_symbol on model_evaluations (symbol);

-- Watchlists: per-business symbol watchlist with alert thresholds.
create table if not exists watchlists (
    id text primary key,
    business_id text not null,
    symbol text not null,
    threshold_pct real default 3.0,
    enabled boolean default true,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_watchlist_business_symbol on watchlists (business_id, symbol);

-- =====================================================================
-- VIRTUAL PORTFOLIO (PAPER TRADING)
-- =====================================================================

-- Virtual portfolios: simulated investment accounts for "what if I had
-- invested ₹X in Y" analysis — no real money moves.
create table if not exists virtual_portfolios (
    id text primary key,
    business_id text not null,
    name text not null,
    initial_cash real default 0.0,
    cash real default 0.0,
    realized_pnl real default 0.0,
    created_at timestamptz not null default now()
);

create index if not exists idx_virtual_portfolios_business on virtual_portfolios (business_id);

-- Portfolio holdings: current open positions within a virtual portfolio.
create table if not exists portfolio_holdings (
    id text primary key,
    portfolio_id text not null references virtual_portfolios (id) on delete cascade,
    symbol text not null,
    quantity real default 0.0,
    average_cost real default 0.0
);

create unique index if not exists idx_holding_portfolio_symbol on portfolio_holdings (portfolio_id, symbol);

-- Virtual transactions: individual buy/sell trades within virtual portfolios.
create table if not exists virtual_transactions (
    id text primary key,
    portfolio_id text not null references virtual_portfolios (id) on delete cascade,
    business_id text not null,
    symbol text not null,
    side text not null,
    quantity real default 0.0,
    price real default 0.0,
    amount real default 0.0,
    fee real default 0.0,
    realized_pnl real default 0.0,
    executed_at text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_virtual_transactions_business on virtual_transactions (business_id);
create index if not exists idx_virtual_transactions_portfolio on virtual_transactions (portfolio_id);

-- Portfolio snapshots: daily EOD value snapshots for portfolio performance charts.
create table if not exists portfolio_snapshots (
    id text primary key,
    portfolio_id text not null references virtual_portfolios (id) on delete cascade,
    snapshot_date text not null,
    cash real default 0.0,
    invested real default 0.0,
    total_value real default 0.0,
    unrealized_pnl real default 0.0,
    realized_pnl real default 0.0
);

create index if not exists idx_portfolio_snapshots_portfolio on portfolio_snapshots (portfolio_id);

-- =====================================================================
-- FRAUD DETECTION
-- =====================================================================

-- Fraud transactions: raw transactions submitted for anomaly scanning.
create table if not exists fraud_transactions (
    id text primary key,
    business_id text not null,
    transaction_id text not null,
    date text default '',
    amount real,
    vendor text default '',
    transaction_type text default 'payment',
    reference text default '',
    source text default 'upload',
    batch_id text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_fraud_tx_business_external on fraud_transactions (business_id, transaction_id);

-- Fraud alerts: anomalies flagged by the detection engine.
-- status: open | investigating | resolved | dismissed.
create table if not exists fraud_alerts (
    id text primary key,
    business_id text not null,
    transaction_id text not null,
    amount real,
    date text default '',
    vendor text default '',
    risk_level text default 'low',
    reason text default '',
    detection_method text default 'rule',
    recommended_action text default 'Verify with the vendor and reviewer',
    status text default 'open',
    batch_id text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_fraud_alert_business_status on fraud_alerts (business_id, status);

-- Alert reviews: human review decisions attached to fraud alerts.
create table if not exists alert_reviews (
    id text primary key,
    alert_id text not null references fraud_alerts (id) on delete cascade,
    business_id text not null,
    reviewer text default '',
    action text not null,
    note text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_alert_reviews_alert on alert_reviews (alert_id);

-- =====================================================================
-- AUTOMATION / N8N INTEGRATION
-- =====================================================================

-- Workflow configs: n8n workflow registrations per business. Stores the
-- webhook URL, schedule (cron string), and last-run status so the
-- Automation dashboard can show live health.
create table if not exists workflow_configs (
    id text primary key,
    business_id text not null,
    name text not null,
    workflow_type text not null,
    enabled boolean default true,
    webhook_url text default '',
    schedule text default '',
    last_run_at text default '',
    last_status text default 'never_run',
    created_at timestamptz not null default now()
);

create index if not exists idx_workflow_configs_business on workflow_configs (business_id);

-- Webhook events: inbound events received from n8n (or other sources).
-- Idempotent: duplicate event_ids are ignored.
create table if not exists webhook_events (
    event_id text primary key,
    source text default 'n8n',
    event_type text default '',
    business_id text default '',
    payload_json text default '{}',
    status text default 'received',
    received_at timestamptz not null default now()
);

create index if not exists idx_webhook_events_business on webhook_events (business_id);

-- Execution logs: audit trail of every workflow run (automated or manual).
create table if not exists execution_logs (
    id text primary key,
    business_id text default '',
    workflow text not null,
    event_id text default '',
    status text default 'success',
    message text default '',
    duration_ms integer default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_execution_logs_business on execution_logs (business_id);

-- Notifications: in-app alert messages surfaced to the business owner.
-- channel: in_app | email | sms. is_read tracks inbox badge count.
create table if not exists notifications (
    id text primary key,
    business_id text not null,
    title text not null,
    message text default '',
    severity text default 'info',
    channel text default 'in_app',
    is_read boolean default false,
    created_at timestamptz not null default now()
);

create index if not exists idx_notifications_business on notifications (business_id);

-- =====================================================================
-- AI ADVISOR HISTORY
-- =====================================================================

-- Chat messages: conversational history for the AI Advisor (user + assistant turns).
create table if not exists chat_messages (
    id uuid primary key default uuid_generate_v4(),
    business_id uuid not null references businesses (id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    intent text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_chat_messages_business_id on chat_messages (business_id);

-- Conversations: named sessions grouping a series of AI Advisor exchanges.
create table if not exists conversations (
    id text primary key,
    business_id text not null,
    title text default 'New conversation',
    created_at timestamptz not null default now()
);

create index if not exists idx_conversations_business on conversations (business_id);

-- AI interactions: structured log of every advisor request/response with
-- intent classification and RAG source citations for auditability.
create table if not exists ai_interactions (
    id text primary key,
    business_id text not null,
    conversation_id text default '',
    query text default '',
    answer text default '',
    intent text default '',
    sources_json text default '[]',
    created_at timestamptz not null default now()
);

create index if not exists idx_ai_interactions_business on ai_interactions (business_id);

-- =====================================================================
-- REPORTS
-- =====================================================================

-- Reports: metadata for generated PDF/export reports. The blob lives in
-- Supabase Storage; storage_path is the object key.
create table if not exists reports (
    id uuid primary key default uuid_generate_v4(),
    business_id uuid not null references businesses (id) on delete cascade,
    title text not null,
    period text default '',
    storage_path text default '',
    created_at timestamptz not null default now()
);

create index if not exists idx_reports_business_id on reports (business_id);
