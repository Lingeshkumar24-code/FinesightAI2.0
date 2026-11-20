import io


def test_advisor_computes_budget_variance(client, auth_headers):
    resp = client.post(
        "/api/v1/advisor/ask",
        headers=auth_headers,
        json={
            "query": "Did we overspend our marketing budget this quarter?",
            "extracted_params": {
                "budget": {"marketing": 10000},
                "actual": {"marketing": 14000},
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "budget_variance"
    assert body["is_valid"] is True
    assert "marketing" in body["tool_result"]["breaches"]


def test_advisor_missing_params_is_handled_gracefully(client, auth_headers):
    resp = client.post(
        "/api/v1/advisor/ask",
        headers=auth_headers,
        json={"query": "What's our WACC?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    assert "missing" in body["answer"].lower()


def test_document_upload_then_advisor_uses_rag(client, auth_headers):
    file_content = (
        b"Our biggest Q3 operational risk was a single-vendor dependency "
        b"for packaging materials, which caused a two-week shipping delay."
    )
    upload_resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("q3_notes.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["chunks_indexed"] >= 1

    ask_resp = client.post(
        "/api/v1/advisor/ask",
        headers=auth_headers,
        json={"query": "Tell me about our vendor dependency situation."},
    )
    assert ask_resp.status_code == 200
    body = ask_resp.json()
    assert body["route"] == "rag:retrieve"
    assert any("q3_notes.txt" in c for c in body["citations"])


def test_document_upload_rejects_unsupported_type(client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 422


def test_document_upload_extracts_pdf_text(client, auth_headers):
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Q3 revenue was ₹125,000 and net profit was ₹24,000.")
    pdf_bytes = document.tobytes()
    document.close()

    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("financials.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["chunks_indexed"] >= 1


def test_document_upload_extracts_xlsx_values(client, auth_headers):
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Income Statement"
    sheet.append(["Period", "Revenue", "Net Profit"])
    sheet.append(["2026-Q3", 125000, 24000])
    buffer = io.BytesIO()
    workbook.save(buffer)

    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("financials.xlsx", io.BytesIO(buffer.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    assert resp.json()["chunks_indexed"] >= 1


def test_document_upload_extracts_docx_tables(client, auth_headers):
    from docx import Document

    document = Document()
    document.add_paragraph("FY2025 financial summary")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Revenue"
    table.cell(0, 1).text = "125000"
    table.cell(1, 0).text = "Net profit"
    table.cell(1, 1).text = "24000"
    buffer = io.BytesIO()
    document.save(buffer)

    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("financials.docx", io.BytesIO(buffer.getvalue()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunks_indexed"] >= 1


def test_document_upload_rejects_files_over_configured_limit(client, auth_headers, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10)
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("large.txt", io.BytesIO(b"01234567890"), "text/plain")},
    )
    assert resp.status_code == 413


def test_document_upload_rejects_empty_file(client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("empty.txt", io.BytesIO(b"   "), "text/plain")},
    )
    assert resp.status_code == 422


def test_what_if_simulator_endpoint(client, auth_headers):
    resp = client.post(
        "/api/v1/simulator/what-if",
        headers=auth_headers,
        json={
            "starting_revenue": 20000,
            "starting_costs": 15000,
            "starting_cash": 10000,
            "levers": {"monthly_revenue_growth_pct": 3.0},
            "periods": 6,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["periods"]) == 6
    assert body["ending_cash"] > 10000


def test_report_generation_returns_pdf(client, auth_headers):
    resp = client.post(
        "/api/v1/reports/generate",
        headers=auth_headers,
        json={
            "business_name": "Acme Co",
            "period": "2026-Q3",
            "ratios": [{"name": "current_ratio", "value": 2.1, "interpretation": "healthy"}],
            "notes": "Overall healthy quarter.",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 100
