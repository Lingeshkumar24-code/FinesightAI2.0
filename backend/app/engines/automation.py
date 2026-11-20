from __future__ import annotations

from dataclasses import dataclass

_EVENT_RULES = {
    "alert_created": ("New fraud alert", "warning", "Review the flagged transaction in Fraud Detection."),
    "document_verified": ("Document verified", "info", "Extracted fields are ready for review."),
    "forecast_ready": ("Forecast ready", "info", "A new deterministic forecast is available."),
    "budget_breach": ("Budget breach detected", "warning", "Actual spend has exceeded the approved budget."),
    "transaction_imported": ("Transactions imported", "info", "New transactions were added and screened."),
}


@dataclass(frozen=True)
class AutomationOutcome:
    status: str
    message: str
    title: str
    severity: str
    notification_message: str


def evaluate_event(event_type: str, payload: dict) -> AutomationOutcome:
    title, severity, notification_message = _EVENT_RULES.get(
        event_type,
        ("Automation event received", "info", "A webhook event was processed successfully."),
    )

    risk_level = str(payload.get("risk_level", "")).lower()
    if risk_level == "high" or severity == "warning":
        severity = "warning"
    if payload.get("amount") and abs(float(payload["amount"])) >= 200000:
        severity = "critical"

    override_title = payload.get("title")
    if isinstance(override_title, str) and override_title.strip():
        title = override_title.strip()
    override_message = payload.get("message")
    if isinstance(override_message, str) and override_message.strip():
        notification_message = override_message.strip()

    return AutomationOutcome(
        status="success",
        message=f"Processed {event_type} event",
        title=title,
        severity=severity,
        notification_message=notification_message,
    )
