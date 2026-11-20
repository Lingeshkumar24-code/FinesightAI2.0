from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_FIELD_PATTERNS = [
    ("invoice_number", r"(?:invoice|bill)\s*(?:number|no\.?|#)\s*[:#]?\s*([A-Za-z0-9-/]+)", 0.96),
    ("vendor", r"(?:vendor|supplier|issued\s+by|from)\s*[:]\s*([^\n]{2,80})", 0.88),
    ("invoice_date", r"(?:invoice\s+date|date)\s*[:]\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})", 0.90),
    ("total_amount", r"(?:grand\s+total|total\s+amount|amount\s+due|total)[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.94),
    ("tax_amount", r"(?:gst|vat|tax)\s*(?:amount)?[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.85),
    ("gstin", r"\bGSTIN\s*[:#]?\s*([0-9A-Z]{15})\b", 0.97),
    ("revenue", r"(?:total\s+revenue|revenue|sales)[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.92),
    ("net_income", r"(?:net\s+income|profit\s+after\s+tax|PAT)[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.92),
    ("total_assets", r"total\s+assets[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.94),
    ("total_liabilities", r"total\s+liabilities[\s:₹$]*([0-9][0-9,]*(?:\.\d{2})?)", 0.94),
    ("period", r"(?:period|for\s+the\s+period)\s*[:]\s*([A-Za-z0-9][A-Za-z0-9 /-]{2,30})", 0.80),
]

_FINANCIAL_FIELDS = {"revenue", "net_income", "total_assets", "total_liabilities"}


def _to_number(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def extract_fields(text: str, period: str = "") -> list[dict]:
    fields: list[dict] = []
    seen: set[str] = set()
    for name, pattern, confidence in _FIELD_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if name in seen:
            continue
        seen.add(name)
        fields.append({
            "field_name": name,
            "field_value": value,
            "confidence": confidence,
            "verified": False,
            "period": period,
        })

    extracted_period = next((field["field_value"] for field in fields if field["field_name"] == "period"), period)
    if extracted_period:
        for field in fields:
            if not field["period"]:
                field["period"] = extracted_period
    return fields


def cross_check_fields(fields: list[dict], financial_records: list[dict]) -> list[dict]:
    checked = [dict(field) for field in fields]
    for field in checked:
        if field["field_name"] not in _FINANCIAL_FIELDS:
            continue
        extracted_value = _to_number(field["field_value"])
        if extracted_value is None:
            continue
        for record in financial_records:
            if field["period"] and record.get("period") != field["period"]:
                continue
            recorded_value = _to_number(str(record.get(field["field_name"]) or 0))
            if recorded_value is None or recorded_value == 0:
                continue
            if abs(extracted_value - recorded_value) <= abs(recorded_value) * Decimal("0.01"):
                field["verified"] = True
                break
    return checked
