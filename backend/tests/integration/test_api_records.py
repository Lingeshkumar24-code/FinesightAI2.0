from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.config import get_settings


def test_records_dashboard_and_context(client: TestClient, auth_headers: dict[str, str]) -> None:
    records = client.get("/api/v1/financials/records", headers=auth_headers)
    assert records.status_code == 200
    assert len(records.json()) >= 3
    assert all(record["business_id"] == "demo-business-001" for record in records.json())

    dashboard = client.get("/api/v1/financials/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["available"] is True
    assert body["data_label"] == "DEMO DATA"
    assert body["period"] == "2026-Q3"
    assert any(ratio["name"] == "net_margin_pct" for ratio in body["ratios"])
    assert len(body["cash_series"]) == 9

    context = client.get("/api/v1/financials/context", headers=auth_headers)
    assert context.status_code == 200
    context_body = context.json()
    categories = {entry["category"] for entry in context_body["entries"]}
    assert "calculated" in categories
    assert "historical" in categories
    assert "FINANCIAL CONTEXT" in context_body["prompt_context"]


def test_record_upsert_and_tenant_isolation(client: TestClient, auth_headers: dict[str, str]) -> None:
    period = "TEST-Phase1-90210"
    payload = {
        "period": period,
        "revenue": 100000,
        "cogs": 40000,
        "operating_expenses": 20000,
        "net_income": 40000,
        "total_assets": 200000,
        "total_liabilities": 50000,
        "total_equity": 150000,
        "source": "manual",
    }
    created = client.post("/api/v1/financials/records", json=payload, headers=auth_headers)
    assert created.status_code == 200
    record_id = created.json()["id"]
    assert created.json()["verified"] is False

    verified = client.post(f"/api/v1/financials/records/{record_id}/verify", headers=auth_headers)
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    other_token = create_access_token(
        user_id="other@example.com", business_id="other-business", role="owner", settings=get_settings()
    )
    foreign_headers = {"Authorization": f"Bearer {other_token}"}
    blocked = client.post(f"/api/v1/financials/records/{record_id}/verify", headers=foreign_headers)
    assert blocked.status_code == 404

    removed = client.delete(f"/api/v1/financials/records/{record_id}", headers=auth_headers)
    assert removed.status_code == 200
    assert removed.json()["deleted"] == record_id
