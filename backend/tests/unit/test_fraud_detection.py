from app.engines.fraud_detection import detect_fraud, parse_transaction_csv, summarize_fraud


def test_parse_and_detect_fraud() -> None:
    csv_data = (
        b"transaction_id,date,amount,vendor,transaction_type,reference\n"
        b"T-001,2026-11-01,-250000,Acme Corp,payment,INV-1\n"
        b"T-001,2026-11-01,-250000,Acme Corp,payment,INV-1\n"
        b"T-002,2026-11-02,-100,Office Depot,payment,\n"
        b"T-003,2026-11-03,not-a-number,Client A,receipt,R-3\n"
    )
    records, errors = parse_transaction_csv(csv_data)
    assert len(records) == 3
    assert errors and "invalid amount" in errors[0]

    alerts = detect_fraud(records)
    assert len(alerts) >= 2
    assert any(item["transaction_id"] == "T-001" and item["risk_level"] == "high" for item in alerts)
    assert any("duplicate" in item["detection_method"] for item in alerts)

    summary = summarize_fraud(records, alerts)
    assert summary["total_transactions"] == 3
    assert summary["duplicate_count"] >= 2
    assert summary["high_risk_alerts"] >= 1
    assert summary["alerts"] == alerts


def test_vendor_baseline_detection() -> None:
    records = [
        {"transaction_id": f"V-{index}", "date": "2026-11-01", "amount": -100, "vendor": "VendorX", "reference": f"R-{index}"}
        for index in range(4)
    ]
    records.append({"transaction_id": "V-9", "date": "2026-11-05", "amount": -2000, "vendor": "VendorX", "reference": "R-9"})

    alerts = detect_fraud(records)
    outlier = next(item for item in alerts if item["transaction_id"] == "V-9")
    assert outlier["risk_level"] == "high"
    assert "vendor_baseline" in outlier["detection_method"]
