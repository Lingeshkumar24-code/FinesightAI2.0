from app.engines.document_verification import cross_check_fields, extract_fields


def test_extract_invoice_fields() -> None:
    text = """
    Invoice Number: INV-2026-118
    Vendor: Acme Supplies
    Invoice Date: 2026-11-19
    GSTIN: 27AAPFU0939F1ZV
    Total Amount: ₹125,500.00
    Tax Amount: ₹5,500.00
    Period: 2026-Q4
    """
    fields = extract_fields(text)
    by_name = {field["field_name"]: field for field in fields}
    assert by_name["invoice_number"]["field_value"] == "INV-2026-118"
    assert by_name["vendor"]["field_value"] == "Acme Supplies"
    assert by_name["total_amount"]["field_value"] == "125,500.00"
    assert by_name["gstin"]["field_value"] == "27AAPFU0939F1ZV"
    assert all(field["verified"] is False for field in fields)
    assert all(field["period"] == "2026-Q4" for field in fields)


def test_cross_check_financial_fields() -> None:
    text = "Period: 2026-Q4\nRevenue: ₹1,200,000\nNet Income: ₹150,000\nTotal Assets: ₹2,000,000"
    fields = extract_fields(text)
    checked = cross_check_fields(fields, [{
        "period": "2026-Q4",
        "revenue": 1200000,
        "net_income": 150000,
        "total_assets": 2000000,
        "total_liabilities": 800000,
    }])
    by_name = {field["field_name"]: field for field in checked}
    assert by_name["revenue"]["verified"] is True
    assert by_name["net_income"]["verified"] is True
    assert by_name["total_assets"]["verified"] is True
