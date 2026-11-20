import { useEffect, useState, type ChangeEvent } from "react";
import { api, ApiError, type FraudAlert, type FraudSummary, type FraudTransaction, type FraudUpload } from "../lib/api";
import { Card } from "../components/ui/Card";

function money(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function FraudDetection() {
  const [summary, setSummary] = useState<FraudSummary | null>(null);
  const [alerts, setAlerts] = useState<FraudAlert[]>([]);
  const [transactions, setTransactions] = useState<FraudTransaction[]>([]);
  const [upload, setUpload] = useState<FraudUpload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [summaryResult, alertResult, transactionResult] = await Promise.allSettled([
      api.getFraudSummary(),
      api.listFraudAlerts(),
      api.listFraudTransactions(),
    ]);
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    if (alertResult.status === "fulfilled") setAlerts(alertResult.value);
    if (transactionResult.status === "fulfilled") setTransactions(transactionResult.value);
  }

  useEffect(() => {
    void load();
  }, []);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadFraudTransactions(file);
      setUpload(result);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not scan transactions");
    } finally {
      setBusy(false);
    }
  }

  async function review(alert: FraudAlert, action: "confirm" | "dismiss" | "escalate") {
    setBusy(true);
    setError(null);
    try {
      await api.reviewFraudAlert(alert.id, { action, note: `Reviewed from dashboard`, reviewer: "owner" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save review");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="fraud-page">
      <div className="page-header">
        <div>
          <h1>Fraud Detection</h1>
          <p className="page-lead">Deterministic rule-based screening with explainable alerts and an auditable review trail.</p>
        </div>
        <span className="data-badge is-live">rule engine</span>
      </div>

      {error && <div className="page-state is-error"><p className="error-text">{error}</p></div>}

      <div className="stat-strip">
        <div><span>Transactions</span><strong className="num">{summary?.total_transactions ?? 0}</strong></div>
        <div><span>Suspicious</span><strong className="num">{summary?.suspicious_transactions ?? 0}</strong></div>
        <div><span>High Risk</span><strong className="num">{summary?.high_risk_alerts ?? 0}</strong></div>
        <div><span>Duplicates</span><strong className="num">{summary?.duplicate_count ?? 0}</strong></div>
      </div>

      <Card>
        <div className="section-header">
          <h2>Scan Transaction CSV</h2>
          <span className="section-run">transaction_id, date, amount, vendor, reference</span>
        </div>
        <input aria-label="Fraud transaction CSV" type="file" accept=".csv,text/csv" onChange={(e) => void importFile(e)} disabled={busy} />
        {upload && (
          <p className="muted-note mt-3">
            {upload.alerts_created} alerts from {upload.valid} valid rows · {upload.invalid} invalid rows
          </p>
        )}
        {upload && upload.validation_errors.length > 0 && (
          <ul className="assumption-list mt-3">
            {upload.validation_errors.map((item) => <li key={item}>{item}</li>)}
          </ul>
        )}
      </Card>

      <div className="split-grid">
        <Card>
          <div className="section-header"><h2>Open Alerts</h2><span className="section-run">{alerts.length} alerts</span></div>
          <div className="data-table" style={{ maxHeight: 480, overflowY: "auto" }}>
            <table>
              <thead>
                <tr><th>Transaction</th><th>Vendor</th><th className="num">Amount</th><th>Risk</th><th>Reason</th><th>Review</th></tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.transaction_id}</td>
                    <td>{alert.vendor || "—"}</td>
                    <td className="num">{money(alert.amount)}</td>
                    <td><span className={`pill ${alert.risk_level === "high" ? "is-bad" : "is-good"}`}>{alert.risk_level}</span></td>
                    <td style={{ whiteSpace: "normal", minWidth: 260 }} className="muted-note">{alert.reason}</td>
                    <td>
                      <div className="flex gap-2">
                        <button type="button" className="btn btn-primary btn-small" disabled={busy} onClick={() => void review(alert, "confirm")}>Confirm</button>
                        <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => void review(alert, "dismiss")}>Dismiss</button>
                        <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => void review(alert, "escalate")}>Escalate</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {alerts.length === 0 && <tr><td colSpan={6} className="muted-note">No fraud alerts yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <div className="section-header"><h2>Scanned Transactions</h2><span className="section-run">{transactions.length} records</span></div>
          <div className="data-table" style={{ maxHeight: 480, overflowY: "auto" }}>
            <table>
              <thead><tr><th>ID</th><th>Date</th><th>Vendor</th><th className="num">Amount</th></tr></thead>
              <tbody>
                {transactions.map((item) => (
                  <tr key={item.id}>
                    <td>{item.transaction_id}</td><td>{item.date}</td>
                    <td>{item.vendor || "—"}</td><td className="num">{money(item.amount)}</td>
                  </tr>
                ))}
                {transactions.length === 0 && <tr><td colSpan={4} className="muted-note">Upload a CSV to begin.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
