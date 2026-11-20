from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.core.security import TokenPayload, get_current_user
from app.models.schemas import ReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])


def _render_pdf(payload: ReportRequest) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, f"{payload.business_name} — Financial Summary")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(72, y, f"Period: {payload.period}")
    y -= 30

    if payload.ratios:
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, "Key Ratios")
        y -= 18
        c.setFont("Helvetica", 10)
        for ratio in payload.ratios:
            value = "n/a" if ratio.value is None else ratio.value
            c.drawString(80, y, f"{ratio.name}: {value}")
            y -= 14
            if y < 72:
                c.showPage()
                y = height - 72

    if payload.risk:
        y -= 10
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, f"Risk Level: {payload.risk.overall_level.upper()} "
                              f"(score {payload.risk.overall_score}/100)")
        y -= 18
        c.setFont("Helvetica", 10)
        for flag in payload.risk.flags:
            c.drawString(80, y, f"- [{flag.level}] {flag.message}")
            y -= 14
            if y < 72:
                c.showPage()
                y = height - 72

    if payload.notes:
        y -= 10
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, "Notes")
        y -= 18
        c.setFont("Helvetica", 10)
        c.drawString(80, y, payload.notes[:120])

    c.showPage()
    c.save()
    return buffer.getvalue()


@router.post("/generate")
def generate_report(
    payload: ReportRequest, _user: TokenPayload = Depends(get_current_user)
) -> StreamingResponse:
    pdf_bytes = _render_pdf(payload)
    report_id = str(uuid.uuid4())
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report_{report_id}.pdf"',
            "X-Report-Id": report_id,
        },
    )
