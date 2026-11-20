"""Document-specific extraction for the financial RAG pipeline.

The extractor deliberately returns readable, labelled text rather than
silently coercing values into a guessed financial schema. That keeps the
original evidence available to retrieval and lets the analysis layer report
missing or conflicting values instead of inventing them.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status


@dataclass
class ExtractedDocument:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _failure(message: str, exc: Exception | None = None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message if exc is None else f"{message}: {exc}",
    )


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def extract_document(filename: str, raw: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(raw)
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        return _extract_excel(raw, suffix)
    if suffix == ".docx":
        return _extract_docx(raw)
    if suffix == ".csv":
        return _extract_csv(raw)
    if suffix in {".txt", ".md"}:
        try:
            return ExtractedDocument(raw.decode("utf-8-sig"), {"file_type": suffix[1:]})
        except UnicodeDecodeError as exc:
            raise _failure("File is not valid UTF-8 text", exc) from exc
    raise _failure("Unsupported document type")


def _extract_pdf(raw: bytes) -> ExtractedDocument:
    try:
        import fitz

        pages: list[str] = []
        with fitz.open(stream=raw, filetype="pdf") as document:
            for number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(f"=== Page: {number} ===\n{text}")
        if not pages:
            return ExtractedDocument("", {"file_type": "pdf"}, ["PDF contains no extractable text; OCR is required for scanned pages."])
        return ExtractedDocument("\n\n".join(pages), {"file_type": "pdf", "pages": len(pages)})
    except HTTPException:
        raise
    except Exception as exc:
        raise _failure("Failed to parse PDF document", exc) from exc


def _extract_excel(raw: bytes, suffix: str) -> ExtractedDocument:
    try:
        if suffix == ".xls":
            import xlrd

            book = xlrd.open_workbook(file_contents=raw)
            sections: list[str] = []
            for sheet in book.sheets():
                lines = [f"=== Sheet: {sheet.name} ==="]
                for row_index in range(sheet.nrows):
                    values = [_cell(sheet.cell_value(row_index, col)) for col in range(sheet.ncols)]
                    if any(values):
                        lines.append(" | ".join(values))
                if len(lines) > 1:
                    sections.append("\n".join(lines))
            return ExtractedDocument("\n\n".join(sections), {"file_type": "xls", "sheets": len(sections)})

        import openpyxl

        # Load both representations: displayed values are useful evidence,
        # while formulas must remain visible instead of disappearing.
        values_book = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        formula_book = openpyxl.load_workbook(io.BytesIO(raw), data_only=False, read_only=True)
        sections = []
        for sheet_name in values_book.sheetnames:
            values_sheet = values_book[sheet_name]
            formula_sheet = formula_book[sheet_name]
            lines = [f"=== Sheet: {sheet_name} ==="]
            for row_number, (value_row, formula_row) in enumerate(
                zip(values_sheet.iter_rows(), formula_sheet.iter_rows()), start=1
            ):
                cells: list[str] = []
                for value_cell, formula_cell in zip(value_row, formula_row):
                    value = _cell(value_cell.value)
                    formula = _cell(formula_cell.value)
                    if isinstance(formula, str) and formula.startswith("=") and formula != value:
                        cells.append(f"{value} (formula: {formula})" if value else f"formula: {formula}")
                    else:
                        cells.append(value)
                if any(cells):
                    lines.append(f"Row {row_number}: " + " | ".join(cells))
            if len(lines) > 1:
                sections.append("\n".join(lines))
        values_book.close()
        formula_book.close()
        return ExtractedDocument("\n\n".join(sections), {"file_type": "excel", "sheets": len(sections)})
    except Exception as exc:
        raise _failure("Failed to parse Excel workbook", exc) from exc


def _extract_docx(raw: bytes) -> ExtractedDocument:
    try:
        from docx import Document

        document = Document(io.BytesIO(raw))
        lines = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        for index, table in enumerate(document.tables, start=1):
            rows = [" | ".join(_cell(cell.text) for cell in row.cells) for row in table.rows]
            if rows:
                lines.append(f"=== Table: {index} ===\n" + "\n".join(rows))
        return ExtractedDocument("\n\n".join(lines), {"file_type": "docx", "tables": len(document.tables)})
    except Exception as exc:
        raise _failure("Failed to parse DOCX document", exc) from exc


def _extract_csv(raw: bytes) -> ExtractedDocument:
    try:
        decoded = raw.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(decoded))
        lines = [" | ".join(cell.strip() for cell in row) for row in rows if any(cell.strip() for cell in row)]
        return ExtractedDocument("\n".join(lines), {"file_type": "csv", "rows": len(lines)})
    except (UnicodeDecodeError, csv.Error) as exc:
        raise _failure("Failed to parse CSV document", exc) from exc


def extract_text(filename: str, raw: bytes) -> str:
    """Backward-compatible text-only API used by older callers/tests."""
    return extract_document(filename, raw).text
