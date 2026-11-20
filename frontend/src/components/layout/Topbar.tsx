import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../lib/AuthContext";
import { useNavigate } from "react-router-dom";
import { api, type AlertItem } from "../../lib/api";

export function Topbar() {
  const { businessId, logout } = useAuth();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadAlerts() {
      try {
        const data = await api.getAlerts();
        if (!cancelled) setAlerts(data);
      } catch {
        // graceful degrade if unauthenticated
      }
    }
    void loadAlerts();
    return () => {
      cancelled = true;
    };
  }, []);

  const unreadCount = alerts.filter((a) => !a.read).length;

  async function handleTriggerCheck() {
    setChecking(true);
    try {
      const resp = await api.triggerAlertCheck();
      setAlerts(resp.alerts);
    } catch {
      // error handled
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

  return (
    <header className="topbar">
      <div className="topbar-title">
        <span style={{ color: "var(--ink-muted)", fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
          Organization
        </span>
        <div className="tenant-pill">
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#047857" }} />
          <span>{businessId ?? "Acme Global Holdings"}</span>
        </div>
      </div>
      <div className="topbar-aligned" style={{ position: "relative" }}>
        {/* Notification Bell with unread badge */}
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          className="btn btn-secondary"
          style={{ padding: "7px 12px", position: "relative" }}
          aria-label="Alerts and Notifications"
          title="Automated n8n Alert Messages"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {unreadCount > 0 && (
            <span
              style={{
                position: "absolute",
                top: -4,
                right: -4,
                background: "#B91C1C",
                color: "#FFFFFF",
                fontSize: 10,
                fontWeight: 700,
                width: 17,
                height: 17,
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
              }}
            >
              {unreadCount}
            </span>
          )}
        </button>

        {/* Dropdown Popover */}
        {isOpen && (
          <div
            style={{
              position: "absolute",
              top: "120%",
              right: 80,
              width: 380,
              background: "#FFFFFF",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-card)",
              boxShadow: "0 10px 30px rgba(0, 0, 0, 0.15)",
              zIndex: 100,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "var(--surface-raised)",
              }}
            >
              <div>
                <strong style={{ fontSize: 13, color: "var(--ink)" }}>Automated Alert Messages</strong>
                <span style={{ display: "block", fontSize: 11, color: "var(--ink-muted)" }}>
                  Powered by n8n Cloud & Financial Engines
                </span>
              </div>
              <button
                className="btn btn-primary"
                onClick={handleTriggerCheck}
                disabled={checking}
                style={{ padding: "4px 8px", fontSize: 11 }}
              >
                {checking ? "Checking…" : "Run Check"}
              </button>
            </div>

            <div style={{ maxHeight: 320, overflowY: "auto", padding: 8 }}>
              {alerts.length === 0 ? (
                <p style={{ textAlign: "center", color: "var(--ink-muted)", fontSize: 12, padding: "20px 0" }}>
                  No active alert messages. All indicators nominal.
                </p>
              ) : (
                alerts.map((a) => (
                  <div
                    key={a.id}
                    style={{
                      padding: "10px 12px",
                      marginBottom: 6,
                      borderRadius: "var(--radius-soft)",
                      background: a.severity === "critical" ? "#FEF2F2" : a.severity === "watch" ? "#FFFBEB" : "var(--surface-raised)",
                      border: "1px solid " + (a.severity === "critical" ? "#FECACA" : a.severity === "watch" ? "#FDE68A" : "var(--border)"),
                      position: "relative",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                      <span className={`pill is-${a.severity === "critical" ? "bad" : a.severity === "watch" ? "watch" : "good"}`} style={{ fontSize: 9 }}>
                        {a.severity}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--ink-muted)" }}>{a.timestamp}</span>
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink)", marginBottom: 2 }}>{a.title}</div>
                    <p style={{ margin: 0, fontSize: 11.5, color: "var(--ink-soft)", lineHeight: 1.4 }}>{a.message}</p>
                    <button
                      onClick={() => handleDismiss(a.id)}
                      style={{
                        marginTop: 6,
                        background: "transparent",
                        border: "none",
                        color: "var(--ink-muted)",
                        fontSize: 10.5,
                        cursor: "pointer",
                        padding: 0,
                        textDecoration: "underline",
                      }}
                    >
                      Dismiss alert
                    </button>
                  </div>
                ))
              )}
            </div>

            <div
              style={{
                padding: "8px 16px",
                borderTop: "1px solid var(--border)",
                textAlign: "center",
                background: "var(--surface-raised)",
              }}
            >
              <Link
                to="/alerts"
                onClick={() => setIsOpen(false)}
                style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink)" }}
              >
                View Full Automation & Alert Center →
              </Link>
            </div>
          </div>
        )}

        <span style={{ fontSize: "12px", color: "var(--ink-muted)", fontWeight: 500 }}>
          Fiscal Q3 · Real-Time Sync
        </span>
        <button className="btn btn-secondary" onClick={() => { logout(); navigate("/", { replace: true }); }}>
          Sign out
        </button>
      </div>
    </header>
  );
}
