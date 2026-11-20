import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api, type AutomationStatus } from "../lib/api";
import { Automation } from "../pages/Automation";

const status: AutomationStatus = {
  configured: false,
  workflows: [{
    id: "wf-1", name: "Fraud Alert Relay", workflow_type: "alert_created", enabled: true,
    webhook_url: "", schedule: "on_event", last_run_at: "", last_status: "never_run",
  }],
  recent_events: [],
  recent_logs: [{
    id: "log-1", workflow: "Fraud Alert Relay", event_id: "evt-1", status: "success",
    message: "Processed alert_created event", duration_ms: 2, created_at: "2026-11-19T00:00:00Z",
  }],
  notifications: [{
    id: "note-1", title: "New fraud alert", message: "Review the flagged transaction",
    severity: "critical", channel: "in_app", is_read: false, created_at: "2026-11-19T00:00:00Z",
  }],
};

describe("Phase 5 automation page", () => {
  it("renders status and manages workflows, events and notifications", async () => {
    vi.spyOn(api, "getAutomationStatus").mockResolvedValue(status);
    const createWorkflow = vi.spyOn(api, "createWorkflow").mockResolvedValue(status.workflows[0]);
    const runWorkflow = vi.spyOn(api, "runWorkflow").mockResolvedValue(status.recent_logs[0]);
    const receiveWebhook = vi.spyOn(api, "receiveWebhook").mockResolvedValue({
      event_id: "evt-2", source: "n8n", event_type: "alert_created",
      business_id: "demo-business-001", status: "processed", received_at: "2026-11-19T00:00:00Z",
    });
    const markRead = vi.spyOn(api, "markNotificationRead").mockResolvedValue({
      ...status.notifications[0], is_read: true,
    });

    render(<Automation />);
    expect(await screen.findByTestId("automation-page")).toBeInTheDocument();
    expect(screen.getByText("local simulation")).toBeInTheDocument();
    expect(screen.getAllByText("Fraud Alert Relay").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Create workflow" }));
    await waitFor(() => expect(createWorkflow).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Fraud Alert Relay", workflow_type: "alert_created" })
    ));

    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(receiveWebhook).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: "alert_created" })
    ));

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(runWorkflow).toHaveBeenCalledWith("wf-1"));

    fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
    await waitFor(() => expect(markRead).toHaveBeenCalledWith("note-1"));
    vi.restoreAllMocks();
  });
});
