from app.engines.automation import evaluate_event


def test_event_rules_and_payload_overrides() -> None:
    outcome = evaluate_event("alert_created", {"risk_level": "high"})
    assert outcome.status == "success"
    assert outcome.severity == "warning"
    assert outcome.title == "New fraud alert"
    assert "Fraud Detection" in outcome.notification_message

    overridden = evaluate_event("unknown_event", {
        "title": "Custom alert",
        "message": "Custom message",
        "amount": -250000,
    })
    assert overridden.title == "Custom alert"
    assert overridden.notification_message == "Custom message"
    assert overridden.severity == "critical"
