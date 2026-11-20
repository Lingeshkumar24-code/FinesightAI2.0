import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type DashboardSummary, type RatioOut } from "../lib/api";
import { Card } from "../components/ui/Card";

export function Reports() {
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loadingDash, setLoadingDash] = useState(true);

  const [businessName, setBusinessName] = useState("Acme Global Holdings");
  const [period, setPeriod] = useState("2026-Q3");
  const [notes, setNotes] = useState(
    "Consolidated executive briefing covering liquidity ratios, debt structure, and projected cash flows."
  );
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadDashboard() {
      try {
        const data = await api.getDashboard();
        if (cancelled) return;
        setDashboard(data);
        // Pre-populate period from dashboard if available
        if (data.period) setPeriod(data.period);
      } catch {
        // No dashboard data — handled in render
      } finally {
        if (!cancelled) setLoadingDash(false);
      }
    }
    void loadDashboard();
    return () => { cancelled = true; };
  }, []);

  const hasData = dashboard?.available && (dashboard.ratios?.length ?? 0) > 0;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setGenerating(true);
    setError(null);
    setDone(false);
    try {
      const blob = await api.generateReport({
        business_name: businessName,
        period,
        ratios: dashboard?.ratios ?? [],
        risk: dashboard?.risk,
        notes,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${businessName.replace(/\s+/g, "_")}_${period}_report.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Report generation failed");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1>Executive PDF Reports</h1>
        <p className="page-lead">
          Compile certified, board-ready financial intelligence dossiers with ratio benchmarks and audit commentary.
        </p>
      </div>

      {/* Data status banner */}
      {!loadingDash && !hasData && (
        <div style={{
          padding: "14px 16px",
          background: "#FEF3C7",
          border: "1px solid #FDE68A",
          borderRadius: 8,
          color: "#92400E",
          fontSize: 13.5,
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}>
          <span style={{ fontSize: 18 }}>⚠️</span>
          <span>
            Upload financial data first to generate a meaningful report. The PDF will still be created, but will not include ratio analysis.
          </span>
        </div>
      )}

      {/* Report preview — what will be included */}
      {hasData && dashboard?.ratios && dashboard.ratios.length > 0 && (
        <Card>
          <div className="section-header">
            <h2>Report Preview</h2>
            <span className="section-run">{dashboard.ratios.length} ratios included</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--ink-muted)", marginBottom: 12 }}>
            The following financial ratios will be embedded in your PDF report:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {dashboard.ratios.map((ratio: RatioOut) => (
              <div key={ratio.name} style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 12px",
                background: "var(--surface-raised)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 13,
              }}>
                <span style={{ fontWeight: 600, color: "var(--ink)" }}>{ratio.name}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <strong style={{ fontVariantNumeric: "tabular-nums" }}>
                    {ratio.value !== null && ratio.value !== undefined
                      ? Number(ratio.value).toFixed(2)
                      : "—"}
                  </strong>
                  <span style={{ fontSize: 11, color: "var(--ink-muted)", maxWidth: 220, textAlign: "right" }}>
                    {ratio.interpretation}
                  </span>
                </span>
              </div>
            ))}
          </div>
          {dashboard.risk && (
            <div style={{
              marginTop: 12,
              padding: "10px 12px",
              background: dashboard.risk.overall_level === "HIGH" ? "#FEE2E2"
                : dashboard.risk.overall_level === "MEDIUM" ? "#FEF3C7"
                : "#ECFDF5",
              border: `1px solid ${dashboard.risk.overall_level === "HIGH" ? "#FECACA"
                : dashboard.risk.overall_level === "MEDIUM" ? "#FDE68A"
                : "#A7F3D0"}`,
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              color: dashboard.risk.overall_level === "HIGH" ? "#B91C1C"
                : dashboard.risk.overall_level === "MEDIUM" ? "#92400E"
                : "#047857",
            }}>
              Risk Level: {dashboard.risk.overall_level} (Score: {dashboard.risk.overall_score}/100)
              {dashboard.risk.flags.length > 0 && (
                <span style={{ fontWeight: 400, marginLeft: 8 }}>
                  · {dashboard.risk.flags.length} flag{dashboard.risk.flags.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
        </Card>
      )}

      <Card>
        <div className="section-header">
          <h2>Report Configuration</h2>
          <span className="section-run">Standard Audit Dossier</span>
        </div>
        <form onSubmit={handleSubmit} style={{ marginTop: 14 }}>
          <div style={{ marginBottom: 14 }}>
            <label htmlFor="biz">Entity Name</label>
            <input id="biz" value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label htmlFor="period">Reporting Period</label>
            <input id="period" value={period} onChange={(e) => setPeriod(e.target.value)} required />
          </div>
          <div style={{ marginBottom: 18 }}>
            <label htmlFor="notes">Executive Commentary &amp; Notes</label>
            <textarea id="notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={generating} style={{ width: "100%" }}>
            {generating ? "Compiling Dossier…" : `Generate PDF${hasData ? " with Live Data" : ""}`}
          </button>
          {error && <p className="error-text" style={{ marginTop: 10, color: "var(--risk)" }}>{error}</p>}
          {done && (
            <div style={{ marginTop: 14, padding: "10px 12px", background: "#ECFDF5", border: "1px solid #A7F3D0", borderRadius: "var(--radius-soft)", color: "#047857", fontSize: 13, fontWeight: 600 }}>
              ✓ Report generated and downloaded successfully.
            </div>
          )}
        </form>
      </Card>
    </div>
  );
}
