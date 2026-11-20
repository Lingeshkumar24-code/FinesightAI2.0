// Base path for every API call. Vite's dev server proxies `/api` to the
// backend, so every call is resolved relative to the served origin and
// forwarded to the backend — no hardcoded host/port the browser must reach.
const API_PREFIX = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (token) {
    localStorage.setItem("finsight_token", token);
  } else {
    localStorage.removeItem("finsight_token");
  }
}

export function loadStoredToken(): string | null {
  const stored = localStorage.getItem("finsight_token");
  authToken = stored;
  return stored;
}

async function request<TResponse>(
  path: string,
  options: RequestInit & { _isRetry?: boolean } = {}
): Promise<TResponse> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  const resp = await fetch(`${API_PREFIX}/${cleanPath}`, { ...options, headers });

  if (!resp.ok) {
    // If token expired or invalid, auto-renew with demo credentials and retry once
    if (resp.status === 401 && !cleanPath.includes("auth/login") && !options._isRetry) {
      try {
        const loginResp = await fetch(`${API_PREFIX}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: "owner@example.com", password: "demo" }),
        });
        if (loginResp.ok) {
          const authData = (await loginResp.json()) as LoginResponse;
          setAuthToken(authData.access_token);
          localStorage.setItem("finsight_business_id", authData.business_id);
          return request<TResponse>(path, { ...options, _isRetry: true });
        }
      } catch {
        setAuthToken(null);
        localStorage.removeItem("finsight_business_id");
      }
    }

    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  const contentType = resp.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await resp.json()) as TResponse;
  }
  return (await resp.blob()) as unknown as TResponse;
}

// --- Types ---

export interface LoginResponse {
  access_token: string;
  token_type: string;
  business_id: string;
}

export interface RatioOut {
  name: string;
  value: number | null;
  interpretation: string;
}

export interface RiskFlagOut {
  code: string;
  message: string;
  level: string;
  metric_value: number | null;
}

export interface RiskResponse {
  overall_score: number;
  overall_level: string;
  flags: RiskFlagOut[];
}

export interface AdvisorResponse {
  intent: string;
  route: string;
  is_valid: boolean;
  tool_result: Record<string, unknown>;
  citations: string[];
  validation_notes: string[];
  answer: string;
}

export interface SimulationPeriodOut {
  period_index: number;
  revenue: number;
  costs: number;
  net_income: number;
  cash_balance: number;
}

export interface WhatIfResponse {
  periods: SimulationPeriodOut[];
  ending_cash: number;
  breakeven_period: number | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  source: string;
  chunks_indexed: number;
}

export interface DashboardSummary {
  available: boolean;
  message?: string;
  source?: string;
  verified?: boolean;
  data_label?: string;
  period?: string;
  periods?: string[];
  records?: Record<string, unknown>[];
  ratios?: RatioOut[];
  risk?: RiskResponse;
  cash_series?: number[];
  cash_runway_months?: number | null;
  cashflow_records?: Record<string, unknown>[];
  profit_margin_pct?: number | null;
}

export interface StockInfo {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  source: string;
  data_status: string;
  as_of: string;
  latest_price: number | null;
  daily_change: number | null;
  daily_change_pct: number | null;
  volume: number | null;
  trend: string;
}

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockHistory {
  symbol: string;
  source: string;
  data_status: string;
  as_of: string;
  points: PricePoint[];
}

export interface IndicatorSeries {
  indicator: string;
  description: string;
  values: { date?: string; value: number | null; signal?: string; ratio?: number }[];
}

export interface IndicatorsResponse {
  symbol: string;
  source: string;
  data_status: string;
  indicators: IndicatorSeries[];
}

export interface PredictionResult {
  id: string;
  symbol: string;
  model: string;
  horizon_days: number;
  predicted_price: number;
  predicted_direction: string;
  lower_bound: number | null;
  upper_bound: number | null;
  last_actual_price: number;
  metrics: {
    mae?: number;
    rmse?: number;
    directional_accuracy?: number;
    sample_size?: number;
    data_status?: string;
    backtest?: Record<string, unknown>[];
  };
  created_at: string;
  target_date: string;
  actual_price: number | null;
  data_source: string;
}

export interface EvaluationResult {
  symbol: string;
  model: string;
  horizon_days: number;
  mae: number;
  rmse: number;
  directional_accuracy: number;
  sample_size: number;
  data_source: string;
  created_at: string;
}

export interface WatchlistItem {
  id: string;
  business_id: string;
  symbol: string;
  threshold_pct: number;
  enabled: boolean;
}

export interface MarketQuote {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  price: number | null;
  change: number | null;
  percent_change: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  previous_close: number | null;
  volume: number | null;
  is_market_open: boolean | null;
  updated_at: string | null;
}

export interface MarketSearchResult {
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  instrument_type: string;
  country: string;
}

export interface InvestmentOutlook {
  symbol: string;
  investment: number;
  horizon_months: number;
  horizon_days: number;
  annualized_return_pct: number;
  annualized_volatility_pct: number;
  sharpe_like: number | null;
  expected_value: number;
  expected_profit: number;
  expected_profit_pct: number;
  best_case_value: number;
  best_case_profit: number;
  worst_case_value: number;
  worst_case_profit: number;
  var_95_value: number;
  var_95_loss: number;
  probability_of_loss_pct: number;
  max_drawdown_pct: number;
  observations: number;
  notes: string[];
  as_of: string;
  latest_close: number | null;
  alert: AlertItem | null;
}

export interface PortfolioHoldingOut {
  symbol: string;
  quantity: number;
  average_cost: number;
  last_price: number;
  market_value: number;
}

export interface Portfolio {
  id: string;
  business_id: string;
  name: string;
  initial_cash: number;
  cash: number;
  invested: number;
  total_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_return_pct: number;
  holdings: PortfolioHoldingOut[];
  created_at: string;
}

export interface Trade {
  id: string;
  portfolio_id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  amount: number;
  fee: number;
  realized_pnl: number;
  executed_at: string;
}

export interface Snapshot {
  id: string;
  portfolio_id: string;
  snapshot_date: string;
  cash: number;
  invested: number;
  total_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
}

export interface MoneyTransaction {
  id: string;
  business_id: string;
  date: string;
  amount: number;
  category: string;
  description: string;
  vendor: string;
  department: string;
  reference: string;
  source: string;
  ai_categorized: boolean;
  created_at: string;
}

export interface TransactionImport {
  imported: number;
  skipped: number;
  errors: string[];
  categories: Record<string, number>;
}

export interface Budget {
  id: string;
  business_id: string;
  period: string;
  scope: string;
  category: string;
  department: string;
  project: string;
  budgeted_amount: number;
  created_at: string;
}

export interface VarianceItem {
  category: string;
  budgeted: number;
  actual: number;
  variance_abs: number;
  variance_pct: number;
  severity: string;
  favorable: boolean;
  explanation: string;
}

export interface VarianceAnalysis {
  period: string;
  items: VarianceItem[];
  total_budgeted: number;
  total_actual: number;
  total_variance_pct: number;
  narrative: string;
  revenue_context: { revenue: number; spend_as_pct_of_revenue: number | null };
}

export interface CashFlowRecord {
  id: string;
  business_id: string;
  period: string;
  opening_cash: number;
  operating_inflow: number;
  operating_outflow: number;
  investing_inflow: number;
  investing_outflow: number;
  financing_inflow: number;
  financing_outflow: number;
  closing_cash: number;
  net_cash_flow: number;
  notes: string;
  created_at: string;
}

export interface CashFlowAnalysis {
  records: CashFlowRecord[];
  latest: CashFlowRecord | null;
  runway_months: number | null;
  runway_note: string;
  average_monthly_burn: number;
  liquidity_note: string;
  monthly: { period: string; inflow: number; outflow: number; net: number }[];
}

export interface CapitalAnalysis {
  records: Record<string, unknown>[];
  metrics: {
    debt_to_equity: number | null;
    debt_to_assets: number | null;
    interest_coverage: number | null;
    wacc_pct: number;
    after_tax_cost_of_debt_pct: number;
  };
  explanations: Record<string, string>;
  recommendation: string;
}

export interface WorkingCapital {
  period: string;
  working_capital: number;
  current_ratio: number | null;
  quick_ratio: number | null;
  receivables: number;
  payables: number;
  inventory: number;
  trend: { period: string; current_ratio: number | null; working_capital: number }[];
}

export interface LoanScenario {
  id: string;
  business_id: string;
  name: string;
  principal: number;
  annual_rate_pct: number;
  tenure_months: number;
  created_at: string;
}

export interface LoanQuote {
  monthly_emi: number;
  total_interest: number;
  total_repayment: number;
  schedule: { month: number; opening_balance: number; interest: number; principal: number; closing_balance: number }[];
}

export interface BusinessForecast {
  metric: string;
  method: string;
  history: { step: number; actual: number; fitted: number }[];
  forecast: { step: number; value: number; lower: number; upper: number }[];
  assumptions: string[];
  uncertainty: { step: number; margin: number; lower: number; upper: number }[];
}

export interface SavedForecast {
  id: string;
  business_id: string;
  metric: string;
  method: string;
  horizon: number;
  points: { step: number; value: number }[];
  assumptions: string[];
  created_at: string;
}

export interface SavedScenario {
  id: string;
  business_id: string;
  name: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
}

export interface FraudTransaction {
  id: string;
  business_id: string;
  transaction_id: string;
  date: string;
  amount: number | null;
  vendor: string;
  transaction_type: string;
  reference: string;
  source: string;
  batch_id: string;
  created_at: string;
}

export interface FraudUpload {
  batch_id: string;
  received: number;
  valid: number;
  invalid: number;
  validation_errors: string[];
  alerts_created: number;
  summary: FraudSummary;
}

export interface FraudAlert {
  id: string;
  transaction_id: string;
  amount: number | null;
  date: string;
  vendor: string;
  risk_level: string;
  reason: string;
  detection_method: string;
  recommended_action: string;
  status: string;
  created_at: string;
}

export interface FraudSummary {
  total_transactions: number;
  suspicious_transactions: number;
  high_risk_alerts: number;
  duplicate_count: number;
  risk_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  alerts: FraudAlert[];
  review_history: Record<string, unknown>[];
}

export interface ExtractedField {
  id: string;
  document_id: string;
  field_name: string;
  field_value: string;
  confidence: number;
  verified: boolean;
  period: string;
}

export interface VerificationDocument {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  chunks: number;
  fields: ExtractedField[];
}

export interface Workflow {
  id: string;
  name: string;
  workflow_type: string;
  enabled: boolean;
  webhook_url: string;
  schedule: string;
  last_run_at: string;
  last_status: string;
}

export interface WebhookEvent {
  event_id: string;
  source: string;
  event_type: string;
  business_id: string;
  status: string;
  received_at: string;
}

export interface ExecutionLog {
  id: string;
  workflow: string;
  event_id: string;
  status: string;
  message: string;
  duration_ms: number;
  created_at: string;
}

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  severity: string;
  channel: string;
  is_read: boolean;
  created_at: string;
}

export interface AutomationStatus {
  configured: boolean;
  workflows: Workflow[];
  recent_events: WebhookEvent[];
  recent_logs: ExecutionLog[];
  notifications: AppNotification[];
}

// --- API surface ---

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  getRatios: (balanceSheet: Record<string, number>, incomeStatement: Record<string, number>) =>
    request<{ ratios: RatioOut[] }>("/financials/ratios", {
      method: "POST",
      body: JSON.stringify({ balance_sheet: balanceSheet, income_statement: incomeStatement }),
    }),

  getDashboard: () => request<DashboardSummary>("/financials/dashboard"),

  getFinancialContext: () =>
    request<{
      business_id: string;
      generated_at: string;
      entries: { category: string; label: string; value: string; source: string }[];
      prompt_context: string;
      periods: string[];
      source_counts: Record<string, number>;
    }>("/financials/context"),

  getMarketSymbols: () =>
    request<{
      default: { symbol: string; name: string; exchange: string }[];
      note: string;
    }>("/market/symbols"),

  getQuote: (symbol: string) =>
    request<StockInfo>(`/market/quote/${encodeURIComponent(symbol)}`),

  getMarketHistory: (symbol: string, days = 400) =>
    request<StockHistory>(`/market/history/${encodeURIComponent(symbol)}?days=${days}`),

  getIndicators: (symbol: string) =>
    request<IndicatorsResponse>(`/market/indicators/${encodeURIComponent(symbol)}`),

  runPrediction: (payload: {
    symbol: string;
    horizon_days: number;
    model: string;
    store?: boolean;
  }) =>
    request<PredictionResult>("/market/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPredictions: (symbol?: string) =>
    request<PredictionResult[]>(`/market/predictions${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""}`),

  getEvaluations: (symbol?: string) =>
    request<EvaluationResult[]>(`/market/evaluations${symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""}`),

  getWatchlist: () => request<WatchlistItem[]>("/market/watchlist"),

  addWatchlist: (symbol: string, thresholdPct = 3) =>
    request<WatchlistItem>("/market/watchlist", {
      method: "POST",
      body: JSON.stringify({ symbol, threshold_pct: thresholdPct, enabled: true }),
    }),

  removeWatchlist: (symbol: string) =>
    request<{ deleted: string }>(`/market/watchlist/${encodeURIComponent(symbol)}`, {
      method: "DELETE",
    }),

  searchMarket: (query: string) =>
    request<MarketSearchResult[]>(`/market/search?q=${encodeURIComponent(query)}`),

  getMarketUsage: () =>
    request<{
      current_usage: number | null;
      plan_limit: number | null;
      daily_usage: number | null;
      plan_daily_limit: number | null;
      plan_category: string;
    } | null>("/market/usage"),

  getInvestmentOutlook: (payload: {
    symbol: string;
    amount: number;
    horizon_months: number;
    cash_available?: number | null;
    monthly_net_income?: number | null;
    notify?: boolean;
  }) =>
    request<InvestmentOutlook>("/market/outlook", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listPortfolios: () => request<Portfolio[]>("/trading/portfolios"),

  createPortfolio: (name: string, initialCash = 100000) =>
    request<Portfolio>("/trading/portfolios", {
      method: "POST",
      body: JSON.stringify({ name, initial_cash: initialCash }),
    }),

  executeTrade: (
    portfolioId: string,
    payload: { symbol: string; side: string; quantity: number; price?: number; fee?: number }
  ) =>
    request<Trade>(`/trading/portfolios/${portfolioId}/trades`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getTransactions: (portfolioId: string) =>
    request<Trade[]>(`/trading/portfolios/${portfolioId}/transactions`),

  takeSnapshot: (portfolioId: string) =>
    request<Snapshot>(`/trading/portfolios/${portfolioId}/snapshot`, { method: "POST" }),

  getSnapshots: (portfolioId: string) =>
    request<Snapshot[]>(`/trading/portfolios/${portfolioId}/snapshots`),

  addMoneyTransaction: (payload: {
    date: string;
    amount: number;
    category?: string;
    description?: string;
    vendor?: string;
    department?: string;
    reference?: string;
    source?: string;
  }) =>
    request<MoneyTransaction>("/money/transactions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listMoneyTransactions: (kind = "all", limit = 100) =>
    request<MoneyTransaction[]>(`/money/transactions?kind=${kind}&limit=${limit}`),

  importMoneyTransactions: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<TransactionImport>("/money/transactions/import", {
      method: "POST",
      body: formData,
    });
  },

  addBudget: (payload: {
    period: string;
    category: string;
    budgeted_amount: number;
    scope?: string;
    department?: string;
    project?: string;
  }) =>
    request<Budget>("/money/budgets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listBudgets: (period?: string) =>
    request<Budget[]>(`/money/budgets${period ? `?period=${encodeURIComponent(period)}` : ""}`),

  getVariance: (period: string) =>
    request<VarianceAnalysis>(`/money/variance/${encodeURIComponent(period)}`),

  addCashFlow: (payload: Record<string, number | string>) =>
    request<CashFlowRecord>("/money/cashflow", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getCashFlowAnalysis: () => request<CashFlowAnalysis>("/money/cashflow/analysis"),

  addCapitalStructure: (payload: Record<string, number | string>) =>
    request<CapitalAnalysis>("/money/capital", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getCapitalAnalysis: () => request<CapitalAnalysis>("/money/capital/analysis"),

  getWorkingCapital: () => request<WorkingCapital>("/money/working-capital"),

  quoteLoan: (payload: { name?: string; principal: number; annual_rate_pct: number; tenure_months: number }) =>
    request<LoanQuote>("/money/loans/quote", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  saveLoan: (payload: { name: string; principal: number; annual_rate_pct: number; tenure_months: number }) =>
    request<LoanScenario>("/money/loans", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listLoans: () => request<LoanScenario[]>("/money/loans"),

  getLoanQuote: (loanId: string) => request<LoanQuote>(`/money/loans/${loanId}/quote`),

  runBusinessForecast: (payload: {
    metric: string;
    series: number[];
    periods_ahead?: number;
    method?: string;
    store?: boolean;
  }) =>
    request<BusinessForecast>("/money/forecast", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listBusinessForecasts: () => request<SavedForecast[]>("/money/forecasts"),

  saveScenario: (name: string, payload: Record<string, unknown>, result: Record<string, unknown>) =>
    request<SavedScenario>("/money/scenarios", {
      method: "POST",
      body: JSON.stringify({ name, payload, result }),
    }),

  listScenarios: () => request<SavedScenario[]>("/money/scenarios"),

  uploadFraudTransactions: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<FraudUpload>("/fraud/transactions/upload", {
      method: "POST",
      body: formData,
    });
  },

  listFraudTransactions: (limit = 100) =>
    request<FraudTransaction[]>(`/fraud/transactions?limit=${limit}`),

  listFraudAlerts: (status?: string) =>
    request<FraudAlert[]>(`/fraud/alerts${status ? `?status_filter=${encodeURIComponent(status)}` : ""}`),

  reviewFraudAlert: (alertId: string, payload: { action: string; note?: string; reviewer?: string }) =>
    request<FraudAlert>(`/fraud/alerts/${alertId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getFraudSummary: () => request<FraudSummary>("/fraud/summary"),

  verifyDocument: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<VerificationDocument>("/verification/documents", {
      method: "POST",
      body: formData,
    });
  },

  listVerificationDocuments: () => request<VerificationDocument[]>("/verification/documents"),

  getVerificationDocument: (documentId: string) =>
    request<VerificationDocument>(`/verification/documents/${documentId}`),

  verifyExtractedField: (fieldId: string, payload: { verified: boolean; field_value?: string }) =>
    request<ExtractedField>(`/verification/fields/${fieldId}/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getAutomationStatus: () => request<AutomationStatus>("/automation/status"),

  listWorkflows: () => request<Workflow[]>("/automation/workflows"),

  createWorkflow: (payload: { name: string; workflow_type: string; webhook_url?: string; schedule?: string; enabled?: boolean }) =>
    request<Workflow>("/automation/workflows", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateWorkflow: (workflowId: string, payload: { name?: string; webhook_url?: string; schedule?: string; enabled?: boolean }) =>
    request<Workflow>(`/automation/workflows/${workflowId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  runWorkflow: (workflowId: string) =>
    request<ExecutionLog>(`/automation/workflows/${workflowId}/run`, { method: "POST" }),

  receiveWebhook: (payload: { event_id?: string; event_type: string; workflow?: string; payload?: Record<string, unknown> }) =>
    request<WebhookEvent>("/automation/webhooks/receive", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listNotifications: (unreadOnly = false) =>
    request<AppNotification[]>(`/automation/notifications?unread_only=${unreadOnly}`),

  markNotificationRead: (notificationId: string) =>
    request<AppNotification>(`/automation/notifications/${notificationId}/read`, { method: "POST" }),

  getRisk: (inputs: Record<string, number | null>) =>
    request<RiskResponse>("/financials/risk", {
      method: "POST",
      body: JSON.stringify(inputs),
    }),

  askAdvisor: (query: string, extractedParams: Record<string, unknown> = {}) =>
    request<AdvisorResponse>("/advisor/ask", {
      method: "POST",
      body: JSON.stringify({ query, extracted_params: extractedParams }),
    }),

  simulateWhatIf: (payload: {
    starting_revenue: number;
    starting_costs: number;
    starting_cash: number;
    levers: Record<string, number>;
    periods: number;
  }) =>
    request<WhatIfResponse>("/simulator/what-if", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<DocumentUploadResponse>("/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  generateReport: (payload: {
    business_name: string;
    period: string;
    ratios: RatioOut[];
    risk?: RiskResponse;
    notes: string;
  }) =>
    request<Blob>("/reports/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getAlerts: () => request<AlertItem[]>("/alerts"),

  triggerAlertCheck: () =>
    request<{
      status: string;
      alerts_generated: number;
      n8n_webhook_dispatched: boolean;
      alerts: AlertItem[];
    }>("/alerts/trigger-check", {
      method: "POST",
    }),

  markAlertRead: (alertId: string) =>
    request<AlertItem>(`/alerts/${alertId}/read`, {
      method: "POST",
    }),

  dismissAlert: (alertId: string) =>
    request<{ status: string; alert_id: string }>(`/alerts/${alertId}`, {
      method: "DELETE",
    }),

  submitFinancialRecord: (payload: Record<string, number | string>) =>
    request<Record<string, unknown>>("/financials/records", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export interface AlertItem {
  id: string;
  business_id: string;
  title: string;
  message: string;
  severity: "info" | "watch" | "critical" | "low";
  source: string;
  timestamp: string;
  read: boolean;
}

