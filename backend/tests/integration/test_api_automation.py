from fastapi.testclient import TestClient

from app.config import get_settings


def test_automation_workflow_webhook_logs_and_notifications(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    settings = get_settings()
    webhook_headers = {
        **auth_headers,
        "X-N8N-Secret": settings.N8N_SHARED_SECRET,
    }
    created = client.post(
        "/api/v1/automation/workflows",
        json={
            "name": "Fraud Alert Relay",
            "workflow_type": "alert_created",
            "webhook_url": "",
            "schedule": "on_event",
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    workflow = created.json()
    assert workflow["last_status"] == "never_run"

    received = client.post(
        "/api/v1/automation/webhooks/receive",
        json={
            "event_id": "evt-phase5-001",
            "event_type": "alert_created",
            "workflow": "Fraud Alert Relay",
            "payload": {"risk_level": "high", "amount": -250000},
        },
        headers=webhook_headers,
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "processed"

    duplicate = client.post(
        "/api/v1/automation/webhooks/receive",
        json={"event_id": "evt-phase5-001", "event_type": "alert_created", "payload": {}},
        headers=webhook_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["event_id"] == "evt-phase5-001"

    status = client.get("/api/v1/automation/status", headers=auth_headers)
    assert status.status_code == 200, status.text
    result = status.json()
    assert result["configured"] is bool(
        settings.N8N_WEBHOOK_URL and settings.N8N_SHARED_SECRET
    )
    assert any(item["name"] == "Fraud Alert Relay" for item in result["workflows"])
    assert any(item["event_id"] == "evt-phase5-001" for item in result["recent_events"])
    assert any(item["message"] == "Processed alert_created event" for item in result["recent_logs"])
    assert any(item["severity"] == "critical" for item in result["notifications"])

    unread = client.get("/api/v1/automation/notifications?unread_only=true", headers=auth_headers)
    assert unread.status_code == 200
    notification = unread.json()[0]

    marked = client.post(
        f"/api/v1/automation/notifications/{notification['id']}/read",
        headers=auth_headers,
    )
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

    run = client.post(
        f"/api/v1/automation/workflows/{workflow['id']}/run",
        headers=auth_headers,
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "success"

    updated = client.patch(
        f"/api/v1/automation/workflows/{workflow['id']}",
        json={"enabled": False, "schedule": "daily"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["schedule"] == "daily"
