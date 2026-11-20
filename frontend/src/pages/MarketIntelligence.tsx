import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type IndicatorsResponse,
  type InvestmentOutlook,
  type MarketSearchResult,
  type PredictionResult,
  type StockHistory,
  type StockInfo,
  type WatchlistItem,
} from "../lib/api";
import { Card } from "../components/ui/Card";
import { LineChart } from "./Dashboard";

// ── Exchange-aware symbol sets ──────────────────────────────────────────────
const EXCHANGE_SYMBOLS: Record<string, string[]> = {
  NSE: ["TCS.NS", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS", "WIPRO.NS", "ADANIENT.NS", "BAJFINANCE.NS"],
  BSE: ["TCS.BO", "RELIANCE.BO", "INFY.BO", "HDFCBANK.BO", "SBIN.BO"],
};

// ── Currency helpers ─────────────────────────────────────────────────────────
function formatPrice(value: number | null | undefined, _symbol: string): string {
  if (value === null || value === undefined) return "—";
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function number(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(2)}${suffix}`;
}

// ── Loan EMI helper ──────────────────────────────────────────────────────────
function calcEMI(principal: number, annualRate: number, months: number): number {
  const r = annualRate / 12 / 100;
  if (r === 0) return principal / months;
  return (principal * r * Math.pow(1 + r, months)) / (Math.pow(1 + r, months) - 1);
}

// ── Risk level helper ─────────────────────────────────────────────────────────
function getRiskLevel(volatility: number): { label: string; color: string; pct: number } {
  if (volatility < 15) return { label: "Low", color: "#047857", pct: 25 };
  if (volatility < 30) return { label: "Medium", color: "#B45309", pct: 50 };
  if (volatility < 50) return { label: "High", color: "#DC2626", pct: 75 };
  return { label: "Very High", color: "#7C3AED", pct: 100 };
}

export function MarketIntelligence() {
  const [exchange, setExchange] = useState<"NSE" | "BSE">("NSE");
  const [symbol, setSymbol] = useState("TCS.NS");
  const [draftSymbol, setDraftSymbol] = useState("TCS.NS");
  const [horizon, setHorizon] = useState(1);
  const [model, setModel] = useState("linear_regression");
  const [quote, setQuote] = useState<StockInfo | null>(null);
  const [history, setHistory] = useState<StockHistory | null>(null);
  const [indicators, setIndicators] = useState<IndicatorsResponse | null>(null);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchDraft, setWatchDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Benchmark search + "what could I make or lose?" outlook
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<MarketSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [benchSymbol, setBenchSymbol] = useState("TCS.NS");
  const [amount, setAmount] = useState(50000);            // ₹50k default
  const [outlookHorizon, setOutlookHorizon] = useState(12);
  const [cashAvailable, setCashAvailable] = useState<number | "">(500000);   // ₹5 lakh
  const [monthlyIncome, setMonthlyIncome] = useState<number | "">(80000);    // ₹80k/month
  const [outlook, setOutlook] = useState<InvestmentOutlook | null>(null);
  const [outlookLoading, setOutlookLoading] = useState(false);
  const [outlookError, setOutlookError] = useState<string | null>(null);
  const [notifyMsg, setNotifyMsg] = useState<string | null>(null);
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [aiCitations, setAiCitations] = useState<string[]>([]);
  const [aiLoading, setAiLoading] = useState(false);

  const currencySymbol = "₹";

  const load = useCallback(async (target: string) => {
    setLoading(true);
    setError(null);
    try {
      const [quoteData, historyData, indicatorData, predictionData, watchData] = await Promise.all([
        api.getQuote(target),
        api.getMarketHistory(target, 400),
        api.getIndicators(target),
        api.getPredictions(target),
        api.getWatchlist(),
      ]);
      setQuote(quoteData);
      setHistory(historyData);
      setIndicators(indicatorData);
      setPrediction(predictionData[0] ?? null);
      setWatchlist(watchData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load market data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(symbol);
  }, [symbol, load]);

  function submitSymbol(event: FormEvent) {
    event.preventDefault();
    const next = draftSymbol.trim().toUpperCase();
    if (next) setSymbol(next);
  }

  async function runPrediction(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setActionError(null);
    try {
      const result = await api.runPrediction({ symbol, horizon_days: horizon, model, store: true });
      setPrediction(result);
      const stored = await api.getPredictions(symbol);
      setPrediction(stored[0] ?? result);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Prediction failed");
    } finally {
      setBusy(false);
    }
  }

  async function addToWatchlist(event: FormEvent) {
    event.preventDefault();
    const next = watchDraft.trim().toUpperCase();
    if (!next) return;
    setActionError(null);
    try {
      await api.addWatchlist(next);
      setWatchDraft("");
      setWatchlist(await api.getWatchlist());
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update watchlist");
    }
  }

  async function removeFromWatchlist(target: string) {
    setActionError(null);
    try {
      await api.removeWatchlist(target);
      setWatchlist(await api.getWatchlist());
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update watchlist");
    }
  }

  // Debounced company search
  useEffect(() => {
    const term = searchTerm.trim();
    if (term.length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const results = await api.searchMarket(term);
        if (!cancelled) setSearchResults(results);
      } catch {
        if (!cancelled) setSearchResults([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 450);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchTerm]);

  function pickBenchmark(result: MarketSearchResult) {
    setBenchSymbol(result.symbol);
    setSearchTerm("");
    setSearchResults([]);
    setOutlook(null);
    setNotifyMsg(null);
    setAiAnswer(null);
    setAiCitations([]);
    setOutlookError(null);
  }

  async function runOutlook(notify = false) {
    if (!Number.isFinite(amount) || amount <= 0) {
      setOutlookError("Enter an amount greater than zero.");
      return;
    }
    setOutlookLoading(true);
    setOutlookError(null);
    setNotifyMsg(null);
    setAiAnswer(null);
    setAiCitations([]);
    try {
      const data = await api.getInvestmentOutlook({
        symbol: benchSymbol,
        amount,
        horizon_months: outlookHorizon,
        cash_available: cashAvailable === "" ? null : Number(cashAvailable),
        monthly_net_income: monthlyIncome === "" ? null : Number(monthlyIncome),
        notify,
      });
      setOutlook(data);
      if (notify) {
        setNotifyMsg(
          data.alert
            ? "Alert raised in the feed and dispatched to n8n."
            : "Alert raised in the feed."
        );
      }
    } catch (err) {
      setOutlookError(err instanceof ApiError ? err.message : "Failed to compute the outlook");
    } finally {
      setOutlookLoading(false);
    }
  }

  async function explainWithAi() {
    if (!outlook) return;
    setAiLoading(true);
    setAiAnswer(null);
    setAiCitations([]);
    const cur = "₹";
    try {
      const prompt =
        `I am considering investing ${cur}${outlook.investment.toLocaleString()} in ${outlook.symbol} ` +
        `for ${outlook.horizon_months} months. The model expects ${cur}${Math.round(outlook.expected_value).toLocaleString()} ` +
        `back (${outlook.expected_profit_pct.toFixed(1)}% profit), with an 80% range of ` +
        `${cur}${Math.round(outlook.worst_case_value).toLocaleString()} to ${cur}${Math.round(outlook.best_case_value).toLocaleString()}, ` +
        `a 95% value-at-risk loss of ${cur}${Math.round(outlook.var_95_loss).toLocaleString()}, ` +
        `a ${outlook.probability_of_loss_pct.toFixed(0)}% modelled chance of a loss, ${outlook.annualized_volatility_pct.toFixed(0)}% annual volatility ` +
        `and a ${outlook.max_drawdown_pct.toFixed(0)}% worst drawdown last year. ` +
        `My available cash is ${cur}${cashAvailable === "" ? "unknown" : Number(cashAvailable).toLocaleString()} and my monthly net income is ` +
        `${cur}${monthlyIncome === "" ? "unknown" : Number(monthlyIncome).toLocaleString()}. ` +
        `Should I invest, how much should I commit, and what risk does it add to my business cash flow? ` +
        `Use my uploaded financial documents and recorded transactions where relevant.`;
      const resp = await api.askAdvisor(prompt, {
        investment_outlook: {
          symbol: outlook.symbol,
          amount: outlook.investment,
          horizon_months: outlook.horizon_months,
          expected_profit: outlook.expected_profit,
          worst_case_profit: outlook.worst_case_profit,
          var_95_loss: outlook.var_95_loss,
          probability_of_loss_pct: outlook.probability_of_loss_pct,
        },
      });
      setAiAnswer(resp.answer);
      setAiCitations(resp.citations);
    } catch (err) {
      setAiAnswer(err instanceof ApiError ? err.message : "The advisor is unavailable right now.");
    } finally {
      setAiLoading(false);
    }
  }

  const closes = (history?.points ?? []).map((point) => point.close);
  const isDemo = quote?.data_status === "DEMO" || quote?.data_status === "CACHED";

  // ── Derived outlook data for the enhanced analysis card ──────────────────
  const cash = cashAvailable === "" ? 0 : Number(cashAvailable);
  const canAfford = cash >= amount;
  const loanNeeded = canAfford ? 0 : amount - cash;
  const loanEMI = loanNeeded > 0 ? calcEMI(loanNeeded, 10, 36) : 0; // 10% p.a., 36 months
  const sharpeRatio = outlook
    ? (outlook.annualized_return_pct - 6) / (outlook.annualized_volatility_pct || 1)
    : null;
  const riskInfo = outlook ? getRiskLevel(outlook.annualized_volatility_pct) : null;

  // Sharpe-based recommendation
  let recBoxStyle = {};
  let recText = "";
  if (sharpeRatio !== null) {
    if (sharpeRatio > 0.5) {
      recBoxStyle = { background: "#D1FAE5", border: "1px solid #6EE7B7", color: "#065F46" };
      recText = `✅ GOOD BUY opportunity — Sharpe ${sharpeRatio.toFixed(2)} (risk-adjusted returns are strong)`;
    } else if (sharpeRatio >= 0) {
      recBoxStyle = { background: "#FEF3C7", border: "1px solid #FCD34D", color: "#92400E" };
      recText = `⚠️ MODERATE — Sharpe ${sharpeRatio.toFixed(2)} (decent but watch the risk)`;
    } else {
      recBoxStyle = { background: "#FEE2E2", border: "1px solid #FCA5A5", color: "#991B1B" };
      recText = `🚫 CAUTION — Sharpe ${sharpeRatio.toFixed(2)} (returns don't justify the risk)`;
    }
  }

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="market-page">
      <div className="page-header">
        <div>
          <div className="page-kicker">
            <h1>Market Intelligence</h1>
            {quote && (
              <span className={`data-badge ${isDemo ? "is-demo" : "is-live"}`}>
                {quote.data_status.toLowerCase()} data
              </span>
            )}
          </div>
          <p className="page-lead">
            Technical indicators and ML forecasts for Indian equities (NSE/BSE). Historical/delayed prices are never represented as live exchange quotes.
          </p>
        </div>
        <form className="filter-bar" onSubmit={submitSymbol}>
          <label htmlFor="market-symbol">Symbol</label>
          <input
            id="market-symbol"
            value={draftSymbol}
            onChange={(event) => setDraftSymbol(event.target.value)}
            style={{ width: 160 }}
          />
          <button className="btn btn-primary" type="submit" style={{ borderRadius: 8 }}>
            ▶ Load
          </button>
        </form>
      </div>

      {/* ── Exchange Filter Bar ──────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 16px",
          background: "var(--surface-raised, #fff)",
          borderRadius: 12,
          border: "1px solid var(--border)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 13, color: "var(--ink-soft)", marginRight: 4 }}>
          Exchange:
        </span>
        {(["NSE", "BSE"] as const).map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setExchange(ex);
              const first = EXCHANGE_SYMBOLS[ex][0];
              setDraftSymbol(first);
              setSymbol(first);
              setBenchSymbol(first);
            }}
            style={{
              padding: "6px 18px",
              borderRadius: 8,
              border: exchange === ex ? "none" : "1px solid var(--border)",
              background: exchange === ex ? "#0A0A0A" : "transparent",
              color: exchange === ex ? "#fff" : "var(--ink)",
              fontWeight: 600,
              fontSize: 13,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            {ex === "NSE" ? "🇮🇳 NSE" : "🏛 BSE"}
          </button>
        ))}

        <span style={{ marginLeft: 12, fontSize: 12, color: "var(--ink-muted)" }}>
          Quick pick:
        </span>
        {EXCHANGE_SYMBOLS[exchange].map((item) => (
          <button
            key={item}
            type="button"
            style={{
              padding: "4px 12px",
              borderRadius: 20,
              border: symbol === item ? "none" : "1px solid var(--border)",
              background: symbol === item ? "#2563EB" : "var(--surface)",
              color: symbol === item ? "#fff" : "var(--ink)",
              fontSize: 12,
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onClick={() => {
              setDraftSymbol(item);
              setSymbol(item);
            }}
          >
            {item.replace(".NS", "").replace(".BO", "")}
          </button>
        ))}

        <span
          style={{
            marginLeft: "auto",
            fontSize: 20,
            fontWeight: 700,
            color: "#047857",
          }}
        >
          {currencySymbol}
        </span>
      </div>

      {/* ── Company / Ticker Search ──────────────────────────────────────── */}
      <Card>
        <div className="section-header">
          <h2>Company &amp; Ticker Search</h2>
          <span className="section-run">Twelve Data · cached 1 hour · one credit per query</span>
        </div>
        <p className="muted-note" style={{ marginTop: 0 }}>
          Search any listed company or ticker (US, Europe, India, crypto, ETFs) and pick it to
          model an investment.
        </p>
        <div style={{ position: "relative", maxWidth: 420 }}>
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setSearchResults([]);
            }}
            placeholder="e.g. apple, NVDA, Reliance, BTC/USD"
            aria-label="Search company or ticker"
            style={{ width: "100%" }}
          />
          {searchTerm.trim().length >= 2 && (searchResults.length > 0 || searching) && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                left: 0,
                right: 0,
                zIndex: 20,
                background: "var(--surface-raised, #fff)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-soft, 10px)",
                boxShadow: "0 12px 28px rgba(15,23,42,0.12)",
                maxHeight: 280,
                overflowY: "auto",
              }}
            >
              {searching && searchResults.length === 0 && (
                <div style={{ padding: "10px 12px", fontSize: 12, color: "var(--ink-muted)" }}>
                  Searching…
                </div>
              )}
              {searchResults.map((result) => (
                <button
                  key={`${result.symbol}-${result.exchange}`}
                  type="button"
                  onClick={() => pickBenchmark(result)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "8px 12px",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    fontSize: 12.5,
                    color: "var(--ink)",
                  }}
                >
                  <strong>{result.symbol}</strong>{" "}
                  <span style={{ color: "var(--ink-soft)" }}>{result.name}</span>
                  <span style={{ display: "block", fontSize: 11, color: "var(--ink-muted)" }}>
                    {[result.exchange, result.currency, result.instrument_type]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </button>
              ))}
              {!searching && searchResults.length === 0 && (
                <div style={{ padding: "10px 12px", fontSize: 12, color: "var(--ink-muted)" }}>
                  No matches.
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* ── Investment Outlook / "What could I make or lose?" ───────────── */}
      <Card>
        <div className="section-header">
          <h2>Investment Analysis — {benchSymbol}</h2>
          <span className="section-run">
            Deterministic model over real closes · not investment advice
          </span>
        </div>
        <p className="muted-note" style={{ marginTop: 0 }}>
          If you put money into <strong>{benchSymbol}</strong> for a set horizon, how much could you
          gain and how much should you be ready to lose?
        </p>

        <div className="flex flex-wrap items-end gap-3 mt-3">
          <div>
            <label htmlFor="outlook-amount">Amount to invest ({currencySymbol})</label>
            <input
              id="outlook-amount"
              type="number"
              min={1}
              value={amount}
              onChange={(event) => setAmount(Number(event.target.value))}
              style={{ width: 150 }}
            />
          </div>
          <div>
            <label htmlFor="outlook-horizon">Horizon</label>
            <select
              id="outlook-horizon"
              value={outlookHorizon}
              onChange={(event) => setOutlookHorizon(Number(event.target.value))}
            >
              {[3, 6, 12, 24].map((months) => (
                <option key={months} value={months}>
                  {months} months
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="outlook-cash">Cash available ({currencySymbol})</label>
            <input
              id="outlook-cash"
              type="number"
              min={0}
              value={cashAvailable}
              onChange={(event) =>
                setCashAvailable(event.target.value === "" ? "" : Number(event.target.value))
              }
              style={{ width: 150 }}
            />
          </div>
          <div>
            <label htmlFor="outlook-income">Monthly net income ({currencySymbol})</label>
            <input
              id="outlook-income"
              type="number"
              min={0}
              value={monthlyIncome}
              onChange={(event) =>
                setMonthlyIncome(event.target.value === "" ? "" : Number(event.target.value))
              }
              style={{ width: 150 }}
            />
          </div>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => void runOutlook(false)}
            disabled={outlookLoading}
            style={{ borderRadius: 8 }}
          >
            {outlookLoading ? "Calculating…" : "▶ Analyze"}
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => void runOutlook(true)}
            disabled={outlookLoading}
            style={{ borderRadius: 8 }}
          >
            Alert me (n8n)
          </button>
        </div>

        {outlookError && <div className="page-state is-error mt-3"><p className="error-text">{outlookError}</p></div>}
        {notifyMsg && (
          <div className="page-state mt-3">
            <p style={{ color: "#047857", fontWeight: 600, fontSize: 13 }}>{notifyMsg}</p>
          </div>
        )}

        {outlook && (
          <div className="mt-4">
            {/* ── Recommendation Box ─────────────────────────────────────── */}
            {recText && (
              <div
                style={{
                  ...recBoxStyle,
                  borderRadius: 10,
                  padding: "12px 16px",
                  fontWeight: 700,
                  fontSize: 14,
                  marginBottom: 16,
                }}
              >
                {recText}
              </div>
            )}

            {/* ── Can You Afford It? ─────────────────────────────────────── */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: 12,
                marginBottom: 16,
              }}
            >
              {/* Affordability */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: 10,
                  border: `1px solid ${canAfford ? "#6EE7B7" : "#FCA5A5"}`,
                  background: canAfford ? "#F0FDF4" : "#FFF1F2",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Can You Afford It?
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4, color: canAfford ? "#047857" : "#B91C1C" }}>
                  {canAfford ? "✅ Yes" : "⚠️ Short"}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 2 }}>
                  Investing {currencySymbol}{amount.toLocaleString("en-IN")} · Cash {currencySymbol}{cash.toLocaleString("en-IN")}
                </div>
              </div>

              {/* Expected Return */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: 10,
                  border: "1px solid var(--border)",
                  background: "var(--surface-raised)",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Expected Return
                </div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    marginTop: 4,
                    color: outlook.expected_profit >= 0 ? "#047857" : "#B91C1C",
                  }}
                >
                  {outlook.expected_profit >= 0 ? "+" : ""}
                  {currencySymbol}{Math.abs(Math.round(outlook.expected_profit)).toLocaleString("en-IN")}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 2 }}>
                  {outlook.expected_profit_pct >= 0 ? "+" : ""}{outlook.expected_profit_pct.toFixed(1)}% over {outlook.horizon_months} months
                </div>
              </div>

              {/* Risk Level */}
              {riskInfo && (
                <div
                  style={{
                    padding: "14px 16px",
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface-raised)",
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Risk Level
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4, color: riskInfo.color }}>
                    {riskInfo.label}
                  </div>
                  <div style={{ marginTop: 6, height: 6, background: "#E5E7EB", borderRadius: 4 }}>
                    <div
                      style={{
                        width: `${riskInfo.pct}%`,
                        height: "100%",
                        background: riskInfo.color,
                        borderRadius: 4,
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 3 }}>
                    {outlook.annualized_volatility_pct.toFixed(0)}% annual volatility
                  </div>
                </div>
              )}

              {/* Best Case */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: 10,
                  border: "1px solid #6EE7B7",
                  background: "#F0FDF4",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 600, color: "#047857", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  🚀 Best Case (80%)
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4, color: "#047857" }}>
                  +{currencySymbol}{Math.round(outlook.best_case_profit).toLocaleString("en-IN")}
                </div>
                <div style={{ fontSize: 12, color: "#065F46", marginTop: 2 }}>
                  Value: {currencySymbol}{Math.round(outlook.best_case_value).toLocaleString("en-IN")}
                </div>
              </div>

              {/* Worst Case */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: 10,
                  border: "1px solid #FCA5A5",
                  background: "#FFF1F2",
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 600, color: "#B91C1C", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  📉 Worst Case (80%)
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4, color: "#B91C1C" }}>
                  {outlook.worst_case_profit < 0 ? "-" : "+"}
                  {currencySymbol}{Math.abs(Math.round(outlook.worst_case_profit)).toLocaleString("en-IN")}
                </div>
                <div style={{ fontSize: 12, color: "#991B1B", marginTop: 2 }}>
                  95% VaR: −{currencySymbol}{Math.round(outlook.var_95_loss).toLocaleString("en-IN")}
                </div>
              </div>

              {/* Loan recommendation */}
              {loanNeeded > 0 && (
                <div
                  style={{
                    padding: "14px 16px",
                    borderRadius: 10,
                    border: "1px solid #FCD34D",
                    background: "#FFFBEB",
                    gridColumn: "span 2",
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#92400E", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    💰 Should I Take a Loan?
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, marginTop: 6, color: "#78350F" }}>
                    Consider loan of {currencySymbol}{loanNeeded.toLocaleString("en-IN")} at ~10% p.a.
                  </div>
                  <div style={{ fontSize: 13, color: "#92400E", marginTop: 3 }}>
                    EMI would be ≈ {currencySymbol}{Math.round(loanEMI).toLocaleString("en-IN")}/month over 36 months
                  </div>
                  <div style={{ fontSize: 11, color: "#B45309", marginTop: 4 }}>
                    Ensure your monthly income ({currencySymbol}{(monthlyIncome || 0).toLocaleString("en-IN")}) covers the EMI comfortably.
                  </div>
                </div>
              )}
            </div>

            {/* ── Original KPI grid ─────────────────────────────────────── */}
            <div className="kpi-grid">
              <div className="metric">
                <div className="metric-label">Expected value</div>
                <div className="metric-value num">
                  {currencySymbol}{Math.round(outlook.expected_value).toLocaleString("en-IN")}
                </div>
                <div className="metric-note">from {currencySymbol}{outlook.investment.toLocaleString("en-IN")} invested</div>
              </div>
              <div className="metric">
                <div className="metric-label">Chance of loss</div>
                <div
                  className="metric-value num"
                  style={{ color: outlook.probability_of_loss_pct >= 50 ? "#B91C1C" : undefined }}
                >
                  {outlook.probability_of_loss_pct.toFixed(0)}%
                </div>
                <div className="metric-note">modelled probability</div>
              </div>
              <div className="metric">
                <div className="metric-label">Annual volatility</div>
                <div className="metric-value num">{outlook.annualized_volatility_pct.toFixed(0)}%</div>
                <div className="metric-note">
                  return {outlook.annualized_return_pct >= 0 ? "+" : ""}
                  {outlook.annualized_return_pct.toFixed(1)}%/yr
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">Worst drawdown (1y)</div>
                <div className="metric-value num" style={{ color: "#B45309" }}>
                  {outlook.max_drawdown_pct.toFixed(0)}%
                </div>
                <div className="metric-note">{outlook.observations} daily closes</div>
              </div>
            </div>

            <ul className="muted-note" style={{ paddingLeft: 18, lineHeight: 1.7 }}>
              {outlook.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>

            <div className="flex flex-wrap items-center gap-3 mt-3">
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => void explainWithAi()}
                disabled={aiLoading}
                style={{ borderRadius: 8 }}
              >
                {aiLoading ? "Asking the advisor…" : "🤖 Explain with AI (RAG + my documents)"}
              </button>
              <span className="muted-note">
                The advisor reads your uploaded documents and this outlook, then explains the trade-off.
              </span>
            </div>

            {aiAnswer && (
              <div
                className="mt-3"
                style={{
                  padding: "14px 16px",
                  borderRadius: "var(--radius-soft, 10px)",
                  background: "var(--surface-raised, #fff)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                  lineHeight: 1.7,
                  whiteSpace: "pre-wrap",
                  color: "var(--ink)",
                }}
              >
                {aiAnswer}
                {aiCitations.length > 0 && (
                  <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--ink-muted)" }}>
                    Sources: {aiCitations.join(" · ")}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      {error && <div className="page-state is-error"><p className="error-text">{error}</p></div>}
      {actionError && <div className="page-state is-error"><p className="error-text">{actionError}</p></div>}
      {loading && !quote && <div className="skeleton" style={{ height: 220 }} />}

      {quote && (
        <>
          <div className="kpi-grid">
            <div className="metric">
              <div className="metric-label">Last Close</div>
              <div className="metric-value num">{formatPrice(quote.latest_price, symbol)}</div>
              <div className="metric-note">{quote.name} · {quote.as_of}</div>
            </div>
            <div className="metric">
              <div className="metric-label">Daily Change</div>
              <div className="metric-value num" style={{ color: (quote.daily_change ?? 0) >= 0 ? "#047857" : "#B91C1C" }}>
                {number(quote.daily_change)}
              </div>
              <div className="metric-note">{number(quote.daily_change_pct, "%")} versus previous session</div>
            </div>
            <div className="metric">
              <div className="metric-label">Trend</div>
              <div className="metric-value" style={{ fontSize: 20, textTransform: "capitalize" }}>{quote.trend.replace("_", " ")}</div>
              <div className="metric-note">20-session direction</div>
            </div>
            <div className="metric">
              <div className="metric-label">Volume</div>
              <div className="metric-value num" style={{ fontSize: 20 }}>{(quote.volume ?? 0).toLocaleString("en-IN")}</div>
              <div className="metric-note">Source: {quote.source}</div>
            </div>
          </div>

          <Card>
            <div className="section-header">
              <h2>{symbol} Price History</h2>
              <span className="section-run">Adjusted close · {closes.length} sessions</span>
            </div>
            {closes.length > 1 ? (
              <LineChart data={closes} width={720} height={150} color={isDemo ? "#B45309" : "#047857"} />
            ) : (
              <div className="skeleton" style={{ height: 150 }} />
            )}
          </Card>
        </>
      )}

      <div className="market-grid">
        {/* ── ML Price Forecast ───────────────────────────────────────────── */}
        <Card>
          <div className="section-header">
            <h2>ML Price Forecast</h2>
            <span className="section-run">Causal features · walk-forward test</span>
          </div>
          <form className="form-grid-3" onSubmit={runPrediction}>
            <div>
              <label htmlFor="horizon">Horizon</label>
              <select id="horizon" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>
                <option value={1}>1 session</option>
                <option value={5}>5 sessions</option>
                <option value={30}>30 sessions</option>
              </select>
            </div>
            <div>
              <label htmlFor="model">Model</label>
              <select id="model" value={model} onChange={(event) => setModel(event.target.value)}>
                <option value="linear_regression">Linear Regression</option>
                <option value="random_forest">Random Forest</option>
                <option value="xgboost">XGBoost (if installed)</option>
              </select>
            </div>
            <div className="form-action">
              <button className="btn btn-primary" type="submit" disabled={busy || loading} style={{ borderRadius: 8 }}>
                {busy ? "Training…" : "Run forecast"}
              </button>
            </div>
          </form>

          {prediction ? (() => {
            const currentPrice = quote?.latest_price ?? null;
            const predicted = prediction.predicted_price;
            const pctChange = currentPrice && predicted
              ? ((predicted - currentPrice) / currentPrice) * 100
              : null;
            const isUp = pctChange !== null ? pctChange >= 0 : prediction.predicted_direction === "up";
            const investAmount = 10000;
            const predictedInvestValue = currentPrice && predicted
              ? (investAmount / currentPrice) * predicted
              : null;
            const holdingQuantity = currentPrice ? Math.floor(investAmount / currentPrice) : null;
            const holdingCost = holdingQuantity !== null && currentPrice ? holdingQuantity * currentPrice : null;
            const residualCash = holdingCost !== null ? investAmount - holdingCost : null;
            const intervalWidth = prediction.upper_bound != null && prediction.lower_bound != null
              ? prediction.upper_bound - prediction.lower_bound
              : null;

            return (
              <div className="prediction-hero" data-testid="prediction-result">
                {/* Prominent price display */}
                <div
                  style={{
                    padding: "16px",
                    background: isUp ? "#F0FDF4" : "#FFF1F2",
                    borderRadius: 12,
                    border: `1px solid ${isUp ? "#6EE7B7" : "#FCA5A5"}`,
                    marginBottom: 12,
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--ink-muted)", fontWeight: 600, textTransform: "uppercase" }}>
                    Predicted Price in {horizon} session{horizon !== 1 ? "s" : ""}
                  </div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 6 }}>
                    <span style={{ fontSize: 28, fontWeight: 800, color: isUp ? "#047857" : "#B91C1C" }}>
                      {formatPrice(predicted, symbol)}
                    </span>
                    {pctChange !== null && (
                      <span style={{ fontSize: 16, fontWeight: 700, color: isUp ? "#047857" : "#B91C1C" }}>
                        {isUp ? "↑" : "↓"} {Math.abs(pctChange).toFixed(2)}%
                      </span>
                    )}
                  </div>
                  {currentPrice && (
                    <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 4 }}>
                      Current: {formatPrice(currentPrice, symbol)}
                    </div>
                  )}
                </div>

                {/* ₹10k simulation */}
                {predictedInvestValue !== null && (
                  <div
                    style={{
                      padding: "12px 14px",
                      background: "var(--surface-raised)",
                      borderRadius: 10,
                      border: "1px solid var(--border)",
                      fontSize: 13,
                      marginBottom: 12,
                    }}
                  >
                    <strong>If you invest ₹10,000 today</strong>, expected value in {horizon} session{horizon !== 1 ? "s" : ""}:{" "}
                    <span style={{ fontWeight: 700, color: isUp ? "#047857" : "#B91C1C" }}>
                      {formatPrice(predictedInvestValue, symbol)}
                    </span>
                    {" "}
                    <span style={{ color: "var(--ink-muted)", fontSize: 11 }}>
                      ({isUp ? "+" : ""}{((predictedInvestValue - investAmount) / investAmount * 100).toFixed(2)}%)
                    </span>
                  </div>
                )}

                {holdingQuantity !== null && residualCash !== null && (
                  <div
                    style={{
                      padding: "12px 14px",
                      background: "#EFF6FF",
                      borderRadius: 10,
                      border: "1px solid #BFDBFE",
                      fontSize: 13,
                      marginBottom: 12,
                    }}
                  >
                    <strong>Position sizing:</strong> ₹10,000 buys approximately <strong>{holdingQuantity.toLocaleString("en-IN")} share{holdingQuantity === 1 ? "" : "s"}</strong> at the current price, with {money(residualCash)} left over.
                  </div>
                )}

                {/* Confidence interval bar */}
                {prediction.lower_bound != null && prediction.upper_bound != null && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)", marginBottom: 4 }}>
                      95% Confidence Interval
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-soft)", marginBottom: 4 }}>
                      <span>{formatPrice(prediction.lower_bound, symbol)}</span>
                      <span style={{ color: "var(--ink-muted)", fontSize: 10 }}>
                        Range: {intervalWidth ? formatPrice(intervalWidth, symbol) : "—"}
                      </span>
                      <span>{formatPrice(prediction.upper_bound, symbol)}</span>
                    </div>
                    <div style={{ height: 8, background: "#E5E7EB", borderRadius: 4, position: "relative", overflow: "hidden" }}>
                      <div
                        style={{
                          position: "absolute",
                          left: "15%",
                          right: "15%",
                          height: "100%",
                          background: isUp
                            ? "linear-gradient(90deg, #A7F3D0, #059669, #A7F3D0)"
                            : "linear-gradient(90deg, #FCA5A5, #DC2626, #FCA5A5)",
                          borderRadius: 4,
                        }}
                      />
                      {/* Midpoint marker */}
                      <div
                        style={{
                          position: "absolute",
                          left: "50%",
                          transform: "translateX(-50%)",
                          width: 2,
                          height: "100%",
                          background: "white",
                          opacity: 0.7,
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="prediction-metrics">
                  <div><span>MAE</span><strong className="num">{number(prediction.metrics.mae)}</strong></div>
                  <div><span>RMSE</span><strong className="num">{number(prediction.metrics.rmse)}</strong></div>
                  <div><span>Direction Acc.</span><strong className="num">{number(prediction.metrics.directional_accuracy, "%")}</strong></div>
                  <div><span>Test rows</span><strong className="num">{prediction.metrics.sample_size ?? "—"}</strong></div>
                </div>
              </div>
            );
          })() : (
            <p className="muted-note">Run a forecast to see predictions and out-of-sample metrics.</p>
          )}
          <p className="disclaimer">
            Forecasts are probabilistic estimates from historical data, not investment advice or live trading signals.
          </p>
        </Card>

        {/* ── Technical Indicators ─────────────────────────────────────────── */}
        <Card>
          <div className="section-header">
            <h2>Technical Indicators</h2>
            <span className="section-run">Causal rolling windows</span>
          </div>
          {indicators ? (
            <div className="data-table" style={{ maxHeight: 420, overflowY: "auto" }}>
              <table>
                <thead>
                  <tr><th>Indicator</th><th className="num">Latest</th><th>Explanation</th></tr>
                </thead>
                <tbody>
                  {indicators.indicators.map((item) => {
                    const last = item.values[item.values.length - 1];
                    return (
                      <tr key={item.indicator}>
                        <td style={{ fontWeight: 600 }}>{item.indicator.replace(/_/g, " ")}</td>
                        <td className="num">{last ? number(last.value, last.signal ? ` · ${last.signal}` : "") : "—"}</td>
                        <td style={{ color: "var(--ink-muted)", fontSize: 12 }}>{item.description}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="skeleton" style={{ height: 300 }} />
          )}
        </Card>
      </div>

      {/* ── Alert Watchlist ───────────────────────────────────────────────── */}
      <Card>
        <div className="section-header">
          <h2>Alert Watchlist</h2>
          <span className="section-run">Threshold monitoring configuration</span>
        </div>
        <form className="filter-bar" onSubmit={addToWatchlist} data-testid="watchlist-add">
          <label htmlFor="watch-symbol">Add symbol</label>
          <input id="watch-symbol" value={watchDraft} onChange={(event) => setWatchDraft(event.target.value)} style={{ width: 160 }} />
          <button className="btn btn-secondary" type="submit" style={{ borderRadius: 8 }}>
            + Add
          </button>
        </form>
        <div className="data-table mt-3">
          <table>
            <thead><tr><th>Symbol</th><th className="num">Threshold</th><th>Status</th><th /></tr></thead>
            <tbody>
              {watchlist.length === 0 && (
                <tr><td colSpan={4} style={{ color: "var(--ink-muted)" }}>No symbols on the watchlist.</td></tr>
              )}
              {watchlist.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 600 }}>{item.symbol}</td>
                  <td className="num">{item.threshold_pct}%</td>
                  <td><span className={`pill ${item.enabled ? "is-good" : "is-watch"}`}>{item.enabled ? "enabled" : "paused"}</span></td>
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => void removeFromWatchlist(item.symbol)}
                      style={{ borderRadius: 6 }}
                    >
                      ✕ Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
