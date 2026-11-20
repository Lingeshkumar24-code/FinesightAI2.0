import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type AutomationStatus, type Workflow } from "../lib/api";
import { Card } from "../components/ui/Card";

const EVENT_TYPES = ["alert_created", "document_verified", "forecast_ready", "budget_breach", "transaction_imported"];

export function Automation() {
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [name, setName] = useState("Fraud Alert Relay");
  const [workflowType, setWorkflowType] = useState("alert_created");
  const [eventType, setEventType] = useState("alert_created");
  const [riskLevel, setRiskLevel] = useState("high");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setStatus(await api.getAutomationStatus());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load automation status");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function fail(err: unknown, fallback: string) {
    setError(err instanceof ApiError ? err.message : fallback);
  }

  async function createWorkflow(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createWorkflow({ name, workflow_type: workflowType, schedule: "on_event" });
      await load();
    } catch (err) {
      fail(err, "Could not create workflow");
    } finally {
      setBusy(false);
    }
  }

  async function toggleWorkflow(workflow: Workflow) {
    setBusy(true);
    setError(null);
    try {
      await api.updateWorkflow(workflow.id, { enabled: !workflow.enabled });
      await load();
    } catch (err) {
      fail(err, "Could not update workflow");
    } finally {
      setBusy(false);
    }
  }

  async function runWorkflow(workflowId: string) {
    setBusy(true);
    setError(null);
    try {
      await api.runWorkflow(workflowId);
      await load();
    } catch (err) {
      fail(err, "Could not run workflow");
    } finally {
      setBusy(false);
    }
  }

  async function sendEvent() {
    setBusy(true);
    setError(null);
    try {
      await api.receiveWebhook({ event_type: eventType, payload: { risk_level: riskLevel } });
      await load();
    } catch (err) {
      fail(err, "Could not send event");
    } finally {
      setBusy(false);
    }
  }

  async function markRead(notificationId: string) {
    setBusy(true);
    setError(null);
    try {
      await api.markNotificationRead(notificationId);
      await load();
    } catch (err) {
      fail(err, "Could not mark notification as read");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="automation-page">
      <div className="page-header">
        <div>
          <h1>Automation</h1>
          <p className="page-lead">Workflow configuration, webhook event intake, execution logs and in-app notifications.</p>
        </div>
        <span className={`data-badge ${status?.configured ? "is-live" : "is-demo"}`}>
          {status?.configured ? "n8n configured" : "local simulation"}
        </span>
      </div>

      {error && <div className="page-state is-error"><p className="error-text">{error}</p></div>}

      <div className="stat-strip">
        <div><span>Workflows</span><strong className="num">{status?.workflows.length ?? 0}</strong></div>
        <div><span>Recent Events</span><strong className="num">{status?.recent_events.length ?? 0}</strong></div>
        <div><span>Execution Logs</span><strong className="num">{status?.recent_logs.length ?? 0}</strong></div>
        <div><span>Unread Alerts</span><strong className="num">{status?.notifications.filter((item) => !item.is_read).length ?? 0}</strong></div>
      </div>

      <div className="split-grid">
        <Card>
          <div className="section-header"><h2>Create Workflow</h2><span className="section-run">deterministic local runner</span></div>
          <form className="form-grid-2" onSubmit={createWorkflow}>
            <div><label htmlFor="workflow-name">Name</label><input id="workflow-name" value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div><label htmlFor="workflow-type">Event type</label>
              <select id="workflow-type" value={workflowType} onChange={(e) => setWorkflowType(e.target.value)}>
                {EVENT_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div className="form-action"><button className="btn btn-primary" type="submit" disabled={busy}>Create workflow</button></div>
          </form>
          <div className="mt-4">
            <label htmlFor="test-event-type">Send test event</label>
            <div className="flex gap-2 mt-3">
              <select id="test-event-type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
                {EVENT_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <select aria-label="Risk level" value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
                <option value="low">low</option><option value="medium">medium</option><option value="high">high</option>
              </select>
              <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => void sendEvent()}>Send</button>
            </div>
          </div>
        </Card>

        <Card>
          <div className="section-header"><h2>Workflows</h2><span className="section-run">{status?.workflows.length ?? 0} configured</span></div>
          <div className="data-table">
            <table>
              <thead><tr><th>Name</th><th>Type</th><th>Last status</th><th>Enabled</th><th>Action</th></tr></thead>
              <tbody>
                {(status?.workflows ?? []).map((workflow) => (
                  <tr key={workflow.id}>
                    <td>{workflow.name}</td><td>{workflow.workflow_type}</td><td>{workflow.last_status}</td>
                    <td><span className={`pill ${workflow.enabled ? "is-good" : "is-bad"}`}>{workflow.enabled ? "enabled" : "paused"}</span></td>
                    <td>
                      <div className="flex gap-2">
                        <button type="button" className="btn btn-primary btn-small" disabled={busy} onClick={() => void runWorkflow(workflow.id)}>Run</button>
                        <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => void toggleWorkflow(workflow)}>
                          {workflow.enabled ? "Pause" : "Enable"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {status?.workflows.length === 0 && <tr><td colSpan={5} className="muted-note">No workflows configured.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="split-grid">
        <Card>
          <div className="section-header"><h2>Notifications</h2><span className="section-run">in-app channel</span></div>
          <div className="data-table" style={{ maxHeight: 360, overflowY: "auto" }}>
            <table>
              <thead><tr><th>Title</th><th>Severity</th><th>Message</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>
                {(status?.notifications ?? []).map((notification) => (
                  <tr key={notification.id}>
                    <td>{notification.title}</td>
                    <td><span className={`pill ${notification.severity === "critical" || notification.severity === "warning" ? "is-bad" : "is-good"}`}>{notification.severity}</span></td>
                    <td className="muted-note" style={{ whiteSpace: "normal" }}>{notification.message}</td>
                    <td>{notification.is_read ? "read" : "unread"}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-small"
                        disabled={busy || notification.is_read}
                        onClick={() => void markRead(notification.id)}
                      >
                        Mark read
                      </button>
                    </td>
                  </tr>
                ))}
                {status?.notifications.length === 0 && <tr><td colSpan={5} className="muted-note">No notifications yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <div className="section-header"><h2>Recent Execution Logs</h2><span className="section-run">deterministic outcomes</span></div>
          <div className="data-table" style={{ maxHeight: 360, overflowY: "auto" }}>
            <table>
              <thead><tr><th>Workflow</th><th>Event</th><th>Status</th><th className="num">Duration</th></tr></thead>
              <tbody>
                {(status?.recent_logs ?? []).map((log) => (
                  <tr key={log.id}>
                    <td>{log.workflow}</td><td>{log.event_id || "manual"}</td><td>{log.status}</td>
                    <td className="num">{log.duration_ms} ms</td>
                  </tr>
                ))}
                {status?.recent_logs.length === 0 && <tr><td colSpan={4} className="muted-note">No executions yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
