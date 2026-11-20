import { useEffect, useState } from "react";
import { api, type AlertItem } from "../lib/api";
import { Card } from "../components/ui/Card";

export function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchAlerts() {
      try {
        const data = await api.getAlerts();
        if (!cancelled) setAlerts(data);
      } catch {
        if (!cancelled) setStatusMsg("Failed to load alert messages.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void fetchAlerts();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleTriggerCheck() {
    setChecking(true);
    setStatusMsg(null);
    try {
      const resp = await api.triggerAlertCheck();
      setAlerts(resp.alerts);
      setStatusMsg(
        `Automated scan completed: ${resp.alerts_generated} alert(s) generated. ${
          resp.n8n_webhook_dispatched ? "Dispatched webhook to n8n." : "Stored in in-app alert feed."
        }`
      );
    } catch {
      setStatusMsg("Failed to execute automated alert check.");
    } finally {
      setChecking(false);
    }
  }

  async function handleDismiss(id: string) {
    try {
      await api.dismissAlert(id);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // error handled
    }
  }

  const criticalCount = alerts.filter((a) => a.severity === "critical").length;
  const watchCount = alerts.filter((a) => a.severity === "watch").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1>Automation & Alert Stream</h1>
          <p className="page-lead">
            Real-time financial notifications, threshold breaches, and scheduled automated scans powered by n8n.
          </p>
        </div>
        <div className="health-strip">
          <div className="health-metric">
            <span className="health-label">Automation Engine</span>
            <span className="health-value" style={{ fontSize: 15, color: "#047857" }}>
              ● n8n Active
            </span>
          </div>
          <div style={{ height: 24, width: 1, background: "var(--border)" }} />
          <div className="health-metric">
            <span className="health-label">Critical Breaches</span>
            <span className="health-value" style={{ color: criticalCount > 0 ? "#B91C1C" : "var(--ink)" }}>
              {criticalCount}
            </span>
          </div>
          <div style={{ height: 24, width: 1, background: "var(--border)" }} />
          <div className="health-metric">
            <span className="health-label">Watch Items</span>
            <span className="health-value" style={{ color: watchCount > 0 ? "#B45309" : "var(--ink)" }}>
              {watchCount}
            </span>
          </div>
        </div>
      </div>

      {/* Control Banner & Manual Run */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <h3 style={{ margin: "0 0 4px", fontSize: 16 }}>Automated Monitoring Triggers</h3>
            <p style={{ margin: 0, fontSize: 13, color: "var(--ink-muted)" }}>
              Evaluates current ledger, P&L variances, and solvency ratios against regulatory and corporate thresholds.
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleTriggerCheck}
            disabled={checking}
            style={{ padding: "10px 22px" }}
          >
            {checking ? "Executing n8n Scan…" : "Run Automated Risk & Budget Check"}
          </button>
        </div>

        {statusMsg && (
          <div
            style={{
              marginTop: 14,
              padding: "10px 14px",
              borderRadius: "var(--radius-soft)",
              background: "#ECFDF5",
              border: "1px solid #A7F3D0",
              color: "#047857",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            ✓ {statusMsg}
          </div>
        )}
      </Card>

      {/* Alert Feed */}
      <Card>
        <div className="section-header">
          <h2>Active Alert Messages</h2>
          <span className="section-run">{alerts.length} Messages in Feed</span>
        </div>

        {loading ? (
          <p style={{ textAlign: "center", padding: "30px 0", color: "var(--ink-muted)" }}>
            Loading alert stream…
          </p>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <span style={{ fontSize: 32 }}>🛡️</span>
            <h3 style={{ margin: "8px 0 4px" }}>All Systems Nominal</h3>
            <p style={{ margin: 0, color: "var(--ink-muted)", fontSize: 13.5 }}>
              No critical thresholds breached or warnings pending.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 14 }}>
            {alerts.map((a) => (
              <div
                key={a.id}
                style={{
                  padding: "14px 18px",
                  borderRadius: "var(--radius-soft)",
                  background:
                    a.severity === "critical"
                      ? "#FEF2F2"
                      : a.severity === "watch"
                      ? "#FFFBEB"
                      : "var(--surface-raised)",
                  border:
                    "1px solid " +
                    (a.severity === "critical"
                      ? "#FECACA"
                      : a.severity === "watch"
                      ? "#FDE68A"
                      : "var(--border)"),
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span
                      className={`pill is-${a.severity === "critical" ? "bad" : a.severity === "watch" ? "watch" : "good"}`}
                    >
                      {a.severity}
                    </span>
                    <strong style={{ fontSize: 14, color: "var(--ink)" }}>{a.title}</strong>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                      {a.timestamp}
                    </span>
                    <button
                      onClick={() => handleDismiss(a.id)}
                      className="btn btn-secondary"
                      style={{ padding: "4px 8px", fontSize: 11 }}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5 }}>
                  {a.message}
                </p>
                <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                  Source: <strong>{a.source.replace("_", " ").toUpperCase()}</strong> · Monitored Tenant:{" "}
                  <code>{a.business_id}</code>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Integration Reference Card */}
      <Card>
        <div className="section-header">
          <h2>n8n Webhook Endpoint Integration</h2>
          <span className="section-run">External Cloud Integration</span>
        </div>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.6, margin: "0 0 12px" }}>
          To trigger alerts from external n8n workflows, send an HTTP POST request to the webhook receiver:
        </p>
        <div
          style={{
            padding: "12px 14px",
            background: "#0A0A0A",
            color: "#FFFFFF",
            borderRadius: "var(--radius-soft)",
            fontFamily: "var(--font-mono)",
            fontSize: 12.5,
          }}
        >
          POST /api/v1/alerts/webhook
          <br />
          Header: X-N8N-Secret: finsight-n8n-secret
          <br />
          Body: &#123; "business_id": "demo-business-001", "title": "...", "message": "...", "severity": "critical" &#125;
        </div>
      </Card>
    </div>
  );
}
