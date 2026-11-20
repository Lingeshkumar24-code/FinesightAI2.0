from __future__ import annotations

import csv
import io
import statistics
from collections import Counter, defaultdict

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def parse_transaction_csv(content: bytes) -> tuple[list[dict], list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["CSV file is not valid UTF-8 text"]

    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    required = {"transaction_id", "date", "amount"}
    missing = sorted(required - fields)
    if missing:
        return [], [f"Missing required column(s): {', '.join(missing)}"]

    records: list[dict] = []
    errors: list[str] = []
    for row_number, row in enumerate(reader, start=2):
        raw_amount = str(row.get("amount") or "").strip().replace(",", "").replace("₹", "").replace("$", "")
        date = str(row.get("date") or "").strip()
        if not date:
            errors.append(f"Row {row_number}: date is required")
            continue
        try:
            amount = float(raw_amount)
        except ValueError:
            errors.append(f"Row {row_number}: invalid amount {raw_amount!r}")
            continue
        records.append({
            "transaction_id": str(row.get("transaction_id") or "").strip() or f"ROW-{row_number}",
            "date": date,
            "amount": amount,
            "vendor": str(row.get("vendor") or "").strip(),
            "transaction_type": str(row.get("transaction_type") or "payment").strip() or "payment",
            "reference": str(row.get("reference") or "").strip(),
        })
    return records, errors


def _fingerprint(record: dict) -> tuple:
    return (record.get("date", ""), round(abs(record.get("amount") or 0), 2), record.get("vendor", ""), record.get("reference", ""))


def detect_fraud(records: list[dict]) -> list[dict]:
    id_counts = Counter(str(record.get("transaction_id") or "") for record in records)
    fingerprint_counts = Counter(_fingerprint(record) for record in records)

    vendor_amounts: dict[str, list[float]] = defaultdict(list)
    for record in records:
        vendor = str(record.get("vendor") or "").strip().lower()
        if vendor:
            vendor_amounts[vendor].append(abs(record.get("amount") or 0))
    vendor_baselines = {
        vendor: statistics.mean(amounts)
        for vendor, amounts in vendor_amounts.items()
        if len(amounts) >= 3
    }

    findings_by_record: list[list[dict]] = []
    for record in records:
        findings: list[dict] = []
        transaction_id = str(record.get("transaction_id") or "")
        amount = abs(record.get("amount") or 0)
        vendor = str(record.get("vendor") or "").strip()
        reference = str(record.get("reference") or "").strip()

        if id_counts[transaction_id] > 1:
            findings.append({
                "risk_level": "high",
                "reason": f"Transaction identifier appears {id_counts[transaction_id]} times in the batch",
                "detection_method": "duplicate_identifier",
                "recommended_action": "Hold payment and reconcile against the source system",
            })

        if fingerprint_counts[_fingerprint(record)] > 1:
            findings.append({
                "risk_level": "high" if amount >= 50000 else "medium",
                "reason": "Same date, amount, vendor and reference appears more than once",
                "detection_method": "duplicate_fingerprint",
                "recommended_action": "Confirm this is not a double payment before release",
            })

        if amount >= 200000:
            findings.append({
                "risk_level": "high",
                "reason": f"Payment amount {amount:,.2f} exceeds the 200,000 review threshold",
                "detection_method": "amount_threshold",
                "recommended_action": "Obtain dual authorisation before processing",
            })

        baseline = vendor_baselines.get(vendor.lower())
        if baseline and baseline > 0 and amount > 3 * baseline:
            findings.append({
                "risk_level": "high" if amount > 4 * baseline else "medium",
                "reason": f"Payment is {amount / baseline:.1f}x the historical average for {vendor}",
                "detection_method": "vendor_baseline",
                "recommended_action": "Verify the invoice and vendor bank details",
            })

        vendor_history_count = len(vendor_amounts.get(vendor.lower(), []))
        if vendor and vendor_history_count < 3 and amount >= 50000:
            findings.append({
                "risk_level": "medium",
                "reason": f"High-value payment to infrequent vendor {vendor} ({vendor_history_count} prior records)",
                "detection_method": "vendor_frequency",
                "recommended_action": "Confirm vendor identity and purchase order",
            })

        if not reference and amount >= 50000:
            findings.append({
                "risk_level": "medium",
                "reason": "High-value payment has no reference number",
                "detection_method": "missing_reference",
                "recommended_action": "Attach the invoice or remittance reference",
            })

        findings_by_record.append(findings)

    alerts: list[dict] = []
    for record, findings in zip(records, findings_by_record):
        if not findings:
            continue
        top = max(findings, key=lambda item: _RISK_ORDER[item["risk_level"]])
        methods = list(dict.fromkeys(item["detection_method"] for item in findings))
        alerts.append({
            "transaction_id": record.get("transaction_id", ""),
            "amount": record.get("amount"),
            "date": record.get("date", ""),
            "vendor": record.get("vendor", ""),
            "risk_level": top["risk_level"],
            "reason": " | ".join(item["reason"] for item in findings),
            "detection_method": ", ".join(methods),
            "recommended_action": top["recommended_action"],
        })
    return alerts


def summarize_fraud(records: list[dict], alerts: list[dict], reviews: list[dict] | None = None) -> dict:
    review_items = reviews or []
    duplicate_count = sum(count - 1 for count in Counter(str(item.get("transaction_id") or "") for item in records).values() if count > 1)
    duplicate_count += sum(count - 1 for count in Counter(_fingerprint(item) for item in records).values() if count > 1)
    return {
        "total_transactions": len(records),
        "suspicious_transactions": len({alert.get("transaction_id") for alert in alerts if alert.get("transaction_id")}),
        "high_risk_alerts": sum(1 for alert in alerts if alert.get("risk_level") == "high"),
        "duplicate_count": duplicate_count,
        "risk_distribution": dict(Counter(alert.get("risk_level", "low") for alert in alerts)),
        "status_distribution": dict(Counter(alert.get("status", "open") for alert in alerts)),
        "alerts": alerts,
        "review_history": review_items,
    }
