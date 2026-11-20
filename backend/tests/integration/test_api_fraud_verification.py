from fastapi.testclient import TestClient


def test_fraud_upload_alerts_review_and_summary(client: TestClient, auth_headers: dict[str, str]) -> None:
    csv_data = (
        b"transaction_id,date,amount,vendor,transaction_type,reference\n"
        b"FR-001,2026-11-01,-250000,Acme Corp,payment,INV-900\n"
        b"FR-001,2026-11-01,-250000,Acme Corp,payment,INV-900\n"
        b"FR-002,2026-11-02,-250,Stationery Shop,payment,INV-901\n"
    )
    uploaded = client.post(
        "/api/v1/fraud/transactions/upload",
        files={"file": ("fraud.csv", csv_data, "text/csv")},
        headers=auth_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    result = uploaded.json()
    assert result["valid"] == 3
    assert result["alerts_created"] >= 1
    assert result["summary"]["high_risk_alerts"] >= 1

    alerts = client.get("/api/v1/fraud/alerts", headers=auth_headers)
    assert alerts.status_code == 200
    alert = next(item for item in alerts.json() if item["transaction_id"] == "FR-001")

    reviewed = client.post(
        f"/api/v1/fraud/alerts/{alert['id']}/review",
        json={"action": "confirm", "note": "confirmed with finance team", "reviewer": "risk-officer"},
        headers=auth_headers,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "confirmed"

    summary = client.get("/api/v1/fraud/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["status_distribution"].get("confirmed", 0) >= 1
    assert any(item["reviewer"] == "risk-officer" for item in summary.json()["review_history"])

    transactions = client.get("/api/v1/fraud/transactions?limit=10", headers=auth_headers)
    assert transactions.status_code == 200
    assert any(item["transaction_id"] == "FR-002" for item in transactions.json())


def test_document_verification_and_field_confirmation(client: TestClient, auth_headers: dict[str, str]) -> None:
    text = (
        b"Invoice Number: INV-VERIFY-1\n"
        b"Vendor: Acme Supplies\n"
        b"Invoice Date: 2026-11-19\n"
        b"GSTIN: 27AAPFU0939F1ZV\n"
        b"Period: 2026-Q3\n"
        b"Revenue: 310000\n"
        b"Net Income: 58000\n"
        b"Total Amount: 45000\n"
    )
    uploaded = client.post(
        "/api/v1/verification/documents",
        files={"file": ("invoice.txt", text, "text/plain")},
        headers=auth_headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    document = uploaded.json()
    assert document["status"] == "processed"
    assert document["chunks"] >= 1

    by_name = {field["field_name"]: field for field in document["fields"]}
    assert by_name["invoice_number"]["field_value"] == "INV-VERIFY-1"
    assert by_name["gstin"]["field_value"] == "27AAPFU0939F1ZV"
    assert by_name["revenue"]["verified"] is True
    assert by_name["total_amount"]["verified"] is False

    verified = client.post(
        f"/api/v1/verification/fields/{by_name['total_amount']['id']}/verify",
        json={"verified": True, "field_value": "45000.00"},
        headers=auth_headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    assert verified.json()["field_value"] == "45000.00"

    listed = client.get("/api/v1/verification/documents", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == document["id"] for item in listed.json())

    fetched = client.get(f"/api/v1/verification/documents/{document['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert any(field["field_name"] == "vendor" for field in fetched.json()["fields"])
