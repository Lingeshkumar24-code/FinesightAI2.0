import { useEffect, useRef, useState } from "react";
import { api, type DashboardSummary, type RatioOut, ApiError } from "../lib/api";
import { Card } from "../components/ui/Card";

// ── Formatters ────────────────────────────────────────────────────────────────

function inr(value: number | null | undefined): string {
  if (value == null) return "—";
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function fmtRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const rounded = Math.round(value * 1000) / 1000;
  return Number.isInteger(rounded)
    ? `${rounded}`
    : rounded.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}`;
}

// ── Sparkline / Line chart ────────────────────────────────────────────────────

function sparklinePath(series: number[], width: number, height: number) {
  if (!series.length) return { path: "", areaPath: "", dots: [] as number[] };
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = max - min || 1;
  const n = series.length;
  const step = width / Math.max(1, n - 1);
  const pts: number[] = [];
  let path = "";
  for (let i = 0; i < n; i++) {
    const x = i * step;
    const y = height - ((series[i] - min) / range) * (height - 4) - 2;
    pts.push(x, y);
    path += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1) + " ";
  }
  return {
    path,
    areaPath: `${path}L ${((n - 1) * step).toFixed(1)} ${height} L 0 ${height} Z`,
    dots: pts,
  };
}

interface LineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  projectedFrom?: number; // index from which data is "projected"
  labels?: string[];
}

export function LineChart({
  data,
  width = 120,
  height = 44,
  color = "#0F172A",
  projectedFrom,
  labels,
}: LineChartProps) {
  const gradientId = useRef(`chart-grad-${Math.random().toString(36).substring(2, 9)}`).current;
  if (!data.length) return null;

  const actual = projectedFrom != null ? data.slice(0, projectedFrom + 1) : data;
  const projected =
    projectedFrom != null && projectedFrom < data.length - 1
      ? data.slice(projectedFrom)
      : [];

  const { path: actualPath, areaPath, dots } = sparklinePath(actual, width, height);
  const projStep = width / Math.max(1, data.length - 1);

  // Build projected dashed path starting from projectedFrom index
  let projPath = "";
  if (projected.length > 1) {
    for (let i = 0; i < projected.length; i++) {
      const globalIdx = (projectedFrom ?? 0) + i;
      const x = globalIdx * projStep;
      const min = Math.min(...data);
      const max = Math.max(...data);
      const range = max - min || 1;
      const y = height - ((projected[i] - min) / range) * (height - 4) - 2;
      projPath += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1) + " ";
    }
  }

  return (
    <svg
      className="line-chart"
      viewBox={`0 0 ${width} ${height + (labels ? 14 : 0)}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Financial trend chart"
      style={{ overflow: "visible" }}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.20" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
      <path d={actualPath} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {projPath && (
        <path
          d={projPath}
          fill="none"
          stroke={color}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="5,4"
          opacity="0.65"
        />
      )}
      {dots.length >= 2 && (
        <circle
          cx={dots[dots.length - 2]}
          cy={dots[dots.length - 1]}
          r="3"
          fill={color}
          stroke="#FFFFFF"
          strokeWidth="1.5"
        />
      )}
      {labels &&
        labels.map((lbl, i) => {
          const x = (i * width) / Math.max(1, labels.length - 1);
          return (
            <text
              key={lbl}
              x={x}
              y={height + 12}
              fontSize="8"
              fill="var(--ink-muted, #9ca3af)"
              textAnchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"}
            >
              {lbl}
            </text>
          );
        })}
    </svg>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-5 w-full" data-testid="dashboard-skeleton">
      <div className="skeleton" style={{ height: 92 }} />
      <div className="skeleton" style={{ height: 64 }} />
      <Card>
        <div className="kpi-grid">
          {Array.from({ length: 6 }, (_, index) => (
            <div className="skeleton" key={index} style={{ height: 132 }} />
          ))}
        </div>
      </Card>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 20 }}>
        <div className="skeleton" style={{ height: 220 }} />
        <div className="skeleton" style={{ height: 220 }} />
      </div>
    </div>
  );
}

// ── Quick Financial Submission Form ───────────────────────────────────────────

const SAMPLE_DATA = {
  business_name: "Sharma Enterprises Pvt Ltd",
  period: "2026-Q4",
  revenue: 5000000,
  cogs: 2800000,
  operating_expenses: 900000,
  net_income: 1300000,
  total_assets: 8500000,
  total_liabilities: 3200000,
  total_equity: 5300000,
  cash: 1200000,
};

type FormField = keyof typeof SAMPLE_DATA;

const FORM_FIELDS: { key: FormField; label: string; type: "text" | "number"; placeholder?: string }[] = [
  { key: "business_name", label: "Business Name", type: "text", placeholder: "e.g. Sharma Enterprises Pvt Ltd" },
  { key: "period", label: "Period", type: "text", placeholder: "e.g. 2026-Q4" },
  { key: "revenue", label: "Revenue (₹)", type: "number", placeholder: "e.g. 5000000" },
  { key: "cogs", label: "Cost of Goods Sold (₹)", type: "number", placeholder: "e.g. 2800000" },
  { key: "operating_expenses", label: "Operating Expenses (₹)", type: "number", placeholder: "e.g. 900000" },
  { key: "net_income", label: "Net Income (₹)", type: "number", placeholder: "e.g. 1300000" },
  { key: "total_assets", label: "Total Assets (₹)", type: "number", placeholder: "e.g. 8500000" },
  { key: "total_liabilities", label: "Total Liabilities (₹)", type: "number", placeholder: "e.g. 3200000" },
  { key: "total_equity", label: "Total Equity (₹)", type: "number", placeholder: "e.g. 5300000" },
  { key: "cash", label: "Cash (₹)", type: "number", placeholder: "e.g. 1200000" },
];

function FinancialSubmitForm({ onSuccess }: { onSuccess: () => void }) {
  const [form, setForm] = useState<typeof SAMPLE_DATA>({ ...SAMPLE_DATA });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleChange(key: FormField, raw: string) {
    setForm((prev) => ({
      ...prev,
      [key]: key === "business_name" || key === "period" ? raw : raw === "" ? 0 : Number(raw),
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.submitFinancialRecord(form as unknown as Record<string, number | string>);
      onSuccess();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background: "#fff",
        border: "1.5px solid #E5E7EB",
        borderRadius: 16,
        padding: "28px 32px",
        maxWidth: 640,
        margin: "0 auto",
        boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
      }}
    >
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#0A0A0A" }}>Submit Financial Data</h2>
        <p style={{ fontSize: 13, color: "#6B7280", margin: "6px 0 0" }}>
          Pre-filled with sample Indian business data. Adjust values and submit.
        </p>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "14px 20px",
        }}
      >
        {FORM_FIELDS.map(({ key, label, type, placeholder }) => (
          <div key={key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label
              htmlFor={`ff-${key}`}
              style={{ fontSize: 12, fontWeight: 600, color: "#374151", letterSpacing: "0.02em" }}
            >
              {label}
            </label>
            <div style={{ position: "relative" }}>
              {type === "number" && (
                <span
                  style={{
                    position: "absolute",
                    left: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    fontSize: 13,
                    color: "#9CA3AF",
                    pointerEvents: "none",
                  }}
                >
                  ₹
                </span>
              )}
              <input
                id={`ff-${key}`}
                type={type}
                value={String(form[key])}
                onChange={(e) => handleChange(key, e.target.value)}
                placeholder={placeholder}
                style={{
                  width: "100%",
                  padding: type === "number" ? "8px 10px 8px 22px" : "8px 10px",
                  border: "1.5px solid #D1D5DB",
                  borderRadius: 8,
                  fontSize: 13,
                  color: "#0A0A0A",
                  background: "#FAFAFA",
                  boxSizing: "border-box",
                  outline: "none",
                  transition: "border-color 0.15s ease, box-shadow 0.15s ease",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "#0A0A0A";
                  e.target.style.boxShadow = "0 0 0 3px rgba(10,10,10,0.08)";
                  e.target.style.background = "#fff";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "#D1D5DB";
                  e.target.style.boxShadow = "none";
                  e.target.style.background = "#FAFAFA";
                }}
              />
            </div>
          </div>
        ))}
      </div>
      {submitError && (
        <div
          style={{
            marginTop: 14,
            padding: "10px 14px",
            background: "#FEF2F2",
            border: "1px solid #FECACA",
            borderRadius: 8,
            fontSize: 13,
            color: "#B91C1C",
          }}
        >
          {submitError}
        </div>
      )}
      <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
        <button
          type="submit"
          disabled={submitting}
          style={{
            background: "#0A0A0A",
            color: "#fff",
            border: "1.5px solid #0A0A0A",
            borderRadius: 8,
            padding: "10px 24px",
            fontSize: 13.5,
            fontWeight: 600,
            cursor: submitting ? "not-allowed" : "pointer",
            opacity: submitting ? 0.65 : 1,
            transition: "all 0.15s ease",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
          }}
          onMouseEnter={(e) => {
            if (!submitting) {
              (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.transform = "none";
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
          }}
        >
          {submitting ? "Submitting…" : "Submit Financial Data"}
        </button>
        <button
          type="button"
          onClick={() => setForm({ ...SAMPLE_DATA })}
          style={{
            background: "#fff",
            color: "#0A0A0A",
            border: "1.5px solid #0A0A0A",
            borderRadius: 8,
            padding: "10px 20px",
            fontSize: 13.5,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)";
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.transform = "none";
            (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
          }}
        >
          Reset to Sample
        </button>
      </div>
    </form>
  );
}

// ── Cash runway badge ─────────────────────────────────────────────────────────

function RunwayBadge({ months }: { months: number | null | undefined }) {
  if (months == null) return <span style={{ color: "#9CA3AF" }}>N/A</span>;
  const color = months > 12 ? "#059669" : months >= 6 ? "#D97706" : "#DC2626";
  const bg = months > 12 ? "#ECFDF5" : months >= 6 ? "#FFFBEB" : "#FEF2F2";
  const border = months > 12 ? "#6EE7B7" : months >= 6 ? "#FDE68A" : "#FECACA";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 10px",
        borderRadius: 20,
        background: bg,
        border: `1px solid ${border}`,
        color,
        fontWeight: 700,
        fontSize: 13,
      }}
    >
      {months.toFixed(1)} months runway
    </span>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("all");

  async function loadDashboard() {
    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await api.getDashboard();
      setSummary(response);
    } catch (error) {
      setErrorMsg(error instanceof ApiError ? error.message : "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (errorMsg)
    return (
      <div className="page-state is-error">
        <p className="error-text">{errorMsg}</p>
      </div>
    );

  // ── Empty state: show quick-submit form ────────────────────────────────────
  if (!summary?.available) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 32,
          padding: "48px 24px",
        }}
      >
        <div style={{ textAlign: "center", maxWidth: 520 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: "#F3F4F6",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 20px",
              fontSize: 28,
            }}
          >
            📊
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0A0A0A", margin: "0 0 10px" }}>
            No financial records yet
          </h1>
          <p style={{ fontSize: 15, color: "#6B7280", margin: 0, lineHeight: 1.6 }}>
             Upload a verified statement or submit a financial period below to activate your dashboard. The form contains
             editable example values, but nothing is treated as company data until you submit it.
          </p>
        </div>
        <FinancialSubmitForm onSuccess={() => void loadDashboard()} />
      </div>
    );
  }

  // ── Data available ─────────────────────────────────────────────────────────
  const allRatios: RatioOut[] = summary.ratios ?? [];
  const byName = Object.fromEntries(allRatios.map((ratio) => [ratio.name, ratio]));
  const activeWatchCount = summary.risk?.flags.filter((flag) => flag.level !== "low").length ?? 0;
  const cashSeries = summary.cash_series ?? [];
  const cashDisplay = cashSeries.slice(0, 6);
  const periodRecord =
    selectedPeriod === "all"
      ? null
      : (summary.records ?? []).find((record) => record.period === selectedPeriod);

  const netMargin = periodRecord
    ? Number(periodRecord.revenue) > 0
      ? (Number(periodRecord.net_income) / Number(periodRecord.revenue)) * 100
      : null
    : (summary.profit_margin_pct ?? null);

  const banner = byName["net_margin_pct"]?.interpretation
    ? {
        head: "Profitability",
        body: `Net profit margin is ${fmtPct(netMargin)}% — ${byName["net_margin_pct"].interpretation}.`,
        tone: (netMargin ?? 0) >= 0 ? "good" : "bad",
      }
    : null;

  const isDemo = summary.data_label === "DEMO DATA";
  const isVerified = summary.verified === true;

  // Cash runway months
  const runwayMonths = summary.cash_runway_months ?? null;

  // Cash series month labels
  const monthNames = ["M1", "M2", "M3", "M4", "M5", "M6"];
  const cashLabels = cashDisplay.map((_, i) => monthNames[i] ?? `M${i + 1}`);

  const metricCards = [
    {
      name: "Current Ratio",
      fmt: fmtRatio,
      key: "current_ratio",
       series: byName["current_ratio"]?.value == null ? [] : [byName["current_ratio"].value],
      unit: "x",
    },
    {
      name: "Quick Ratio",
      fmt: fmtRatio,
      key: "quick_ratio",
       series: byName["quick_ratio"]?.value == null ? [] : [byName["quick_ratio"].value],
      unit: "x",
    },
    {
      name: "Debt / Equity",
      fmt: fmtRatio,
      key: "debt_to_equity",
       series: byName["debt_to_equity"]?.value == null ? [] : [byName["debt_to_equity"].value],
      unit: "x",
    },
    {
      name: "Gross Margin",
      fmt: fmtPct,
      key: "gross_margin_pct",
       series: byName["gross_margin_pct"]?.value == null ? [] : [byName["gross_margin_pct"].value],
      unit: "%",
    },
    {
      name: "Return on Equity",
      fmt: fmtPct,
      key: "return_on_equity_pct",
       series: byName["return_on_equity_pct"]?.value == null ? [] : [byName["return_on_equity_pct"].value],
      unit: "%",
    },
    {
      name: "Debt / Assets",
      fmt: fmtPct,
      key: "debt_to_assets",
       series: byName["debt_to_assets"]?.value == null ? [] : [byName["debt_to_assets"].value],
      unit: "%",
    },
  ];

  return (
    <div className="page-enter flex flex-col gap-5 w-full">
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <div className="page-kicker" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0 }}>
              {summary.period ? `${summary.period} — ` : ""}Financial Performance Overview
            </h1>
            {isDemo && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "2px 10px",
                  borderRadius: 20,
                  background: "#FFFBEB",
                  border: "1px solid #FDE68A",
                  color: "#D97706",
                  fontWeight: 700,
                  fontSize: 11.5,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                DEMO DATA
              </span>
            )}
            {isVerified && !isDemo && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "2px 10px",
                  borderRadius: 20,
                  background: "#ECFDF5",
                  border: "1px solid #6EE7B7",
                  color: "#059669",
                  fontWeight: 700,
                  fontSize: 11.5,
                  letterSpacing: "0.06em",
                }}
              >
                ✓ VERIFIED
              </span>
            )}
          </div>
          <p className="page-lead">
            Executive summary of liquidity, capital structure and cash projections for {summary.period}.
            {isDemo && " Figures shown are illustrative demo records, not uploaded data."}
          </p>
        </div>

        {/* ── Hero stats strip ── */}
        <div className="health-strip">
          {/* Profit margin hero */}
          <div className="health-metric" style={{ textAlign: "center" }}>
            <span className="health-label">Net Profit Margin</span>
            <span
              className="health-value"
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: (netMargin ?? 0) >= 0 ? "#059669" : "#DC2626",
              }}
            >
              {fmtPct(netMargin)}%
            </span>
          </div>
          <div style={{ height: 40, width: 1, background: "var(--border)" }} />
          {/* Cash runway prominent */}
          <div className="health-metric" style={{ textAlign: "center" }}>
            <span className="health-label">Cash Runway</span>
            <RunwayBadge months={runwayMonths} />
          </div>
          <div style={{ height: 40, width: 1, background: "var(--border)" }} />
          {/* Risk items */}
          <div className="health-run">
            <span className="health-label">Risk Items</span>
            <span className={`pill ${activeWatchCount > 0 ? "is-watch" : "is-good"}`}>
              {activeWatchCount > 0 ? `${activeWatchCount} to review` : "Optimal"}
            </span>
          </div>
        </div>
      </div>

      {/* ── Period selector ── */}
      <div
        className="filter-bar"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          background: "#FAFAFA",
          border: "1px solid #E5E7EB",
          borderRadius: 10,
        }}
      >
        <label
          htmlFor="period-filter"
          style={{ fontSize: 13, fontWeight: 600, color: "#374151", whiteSpace: "nowrap" }}
        >
          Reporting period
        </label>
        <select
          id="period-filter"
          value={selectedPeriod}
          onChange={(event) => setSelectedPeriod(event.target.value)}
          style={{
            padding: "7px 12px",
            borderRadius: 8,
            border: "1.5px solid #D1D5DB",
            fontSize: 13,
            fontWeight: 500,
            background: "#fff",
            color: "#0A0A0A",
            cursor: "pointer",
            outline: "none",
            transition: "border-color 0.15s ease",
          }}
        >
          <option value="all">Latest ({summary.period})</option>
          {(summary.periods ?? []).map((period) => (
            <option key={period} value={period}>
              {period}
            </option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: "#9CA3AF" }}>
          {summary.source ?? "financial record"} · persisted in database
        </span>
      </div>

      {/* ── Profitability insight banner ── */}
      {banner && (
        <div className="insight-banner">
          <div className={`inshead is-${banner.tone}`}>
            <span>
              <strong>{banner.head} Analysis:</strong> {banner.body}
            </span>
          </div>
        </div>
      )}

      {/* ── Core metric KPI grid ── */}
      <Card>
        <div className="section-header">
          <h2>Core Financial Metrics</h2>
          <span className="section-run">Calculated from stored financial records · All monetary values in ₹</span>
        </div>
        <div className="kpi-grid">
          {metricCards.map((metric) => {
            const ratio = byName[metric.key];
            const delta = metric.series[metric.series.length - 1] - metric.series[0];
            return (
              <div className="metric" key={metric.key}>
                <div className="metric-head">
                  <div className="metric-label">{metric.name}</div>
                  <div className="metric-value">
                    {metric.fmt(ratio?.value ?? null)}
                    {ratio?.value !== null && ratio?.value !== undefined && (
                      <span className="unit">{metric.unit}</span>
                    )}
                  </div>
                  <span className={`delta ${delta >= 0 ? "is-up" : "is-down"}`}>
                    {delta >= 0 ? "▲ improving" : "▼ declining"}
                  </span>
                </div>
                <div className="metric-chart">
                  <LineChart data={metric.series} color="#0A0A0A" width={110} height={38} />
                </div>
                {ratio?.interpretation && <div className="metric-note">{ratio.interpretation}</div>}
              </div>
            );
          })}
        </div>
      </Card>

      {/* ── Cash flow + Risk ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 20 }}>
        {cashDisplay.length > 0 && (
          <Card>
            <div className="section-header">
              <h2>Cash-Flow Outlook</h2>
              <span className="section-run">Observed + deterministic projection</span>
            </div>
            <div className="chart-card">
              <div style={{ position: "relative" }}>
                <LineChart
                  data={cashDisplay}
                  color="#047857"
                  width={320}
                  height={100}
                  projectedFrom={Math.max(0, cashDisplay.length - 2)}
                  labels={cashLabels}
                />
                {cashDisplay.length >= 2 && (
                  <span
                    style={{
                      position: "absolute",
                      top: 6,
                      right: 0,
                      fontSize: 10.5,
                      color: "#6B7280",
                      fontStyle: "italic",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <svg width="18" height="6" style={{ display: "inline" }}>
                      <line x1="0" y1="3" x2="18" y2="3" stroke="#047857" strokeWidth="1.8" strokeDasharray="4,3" />
                    </svg>
                    Projected →
                  </span>
                )}
              </div>
              <div className="chart-trend">
                <div>
                  <span className="chart-trend-label">Opening Liquidity</span>
                  <strong className="num">{inr(cashDisplay[0])}</strong>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span className="chart-trend-label">Projected Month 6 Cash</span>
                  <strong className="num" style={{ color: "#047857" }}>
                    {inr(cashDisplay[cashDisplay.length - 1])}
                  </strong>
                </div>
              </div>
            </div>
          </Card>
        )}

        {summary.risk && (
          <Card>
            <div className="section-header">
              <h2>Risk Management &amp; Governance</h2>
              <span className="section-run">Deterministic rule engine</span>
            </div>
            <div className="mt-2" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {summary.risk.flags.length > 0 ? (
                summary.risk.flags.map((flag) => (
                  <div key={flag.code} className="risk-row">
                    <span className={`pill is-${flag.level}`}>{flag.level}</span>
                    <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>{flag.message}</span>
                  </div>
                ))
              ) : (
                <div className="flex items-center gap-3 text-sm" style={{ padding: "16px 0" }}>
                  <span className="pill is-good">All Clear</span>
                  <span style={{ color: "var(--ink-soft)" }}>
                    No critical liquidity or debt thresholds detected.
                  </span>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>

      {/* ── Detailed ratios ledger ── */}
      {allRatios.length > 0 && (
        <Card>
          <div className="section-header">
            <h2>Detailed Financial Ratios Ledger</h2>
            <span className="section-run">Every metric includes a plain-language explanation</span>
          </div>
          <div className="data-table mt-2">
            <table>
              <thead>
                <tr>
                  <th>Financial Indicator</th>
                  <th className="num">Computed Ratio</th>
                  <th>Benchmark Guideline / Interpretation</th>
                </tr>
              </thead>
              <tbody>
                {allRatios.map((ratio) => {
                  let display = "—";
                  if (ratio.value !== null) {
                    if (ratio.name === "debt_to_assets") display = `${(ratio.value * 100).toFixed(1)}%`;
                    else if (["current_ratio", "quick_ratio", "debt_to_equity"].includes(ratio.name))
                      display = `${ratio.value.toFixed(2)}x`;
                    else display = `${ratio.value.toFixed(1)}%`;
                  }
                  return (
                    <tr key={ratio.name}>
                      <td style={{ fontWeight: 600, color: "var(--ink)" }}>
                        {ratio.name.replace(/_/g, " ").toUpperCase()}
                      </td>
                      <td className="num" style={{ fontWeight: 700 }}>
                        {display}
                      </td>
                      <td style={{ color: "var(--ink-soft)" }}>{ratio.interpretation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
