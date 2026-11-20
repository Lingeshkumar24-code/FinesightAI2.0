from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_vector_store
from app.db.session import get_session
from app.core.security import TokenPayload, get_current_user
from app.db.extensions import ExtractedField
from app.db.models import Document, DocumentChunkRow, FinancialRecord
from app.db.util import as_dict, iso
from app.engines.document_verification import cross_check_fields, extract_fields
from app.models.schemas_ext import DocumentOut, ExtractedFieldOut, FieldVerificationIn
from app.rag.ingestion import chunk_document
from app.rag.vectorstore import VectorStore
from app.services.document_extraction import extract_text

router = APIRouter(prefix="/verification", tags=["document-verification"])

_SUPPORTED_SUFFIXES = (".txt", ".csv", ".md", ".xlsx", ".pdf")


def _field_out(field: ExtractedField) -> ExtractedFieldOut:
    data = as_dict(field)
    return ExtractedFieldOut(**{key: data.get(key) for key in ExtractedFieldOut.model_fields})


def _document_out(document: Document, fields: list[ExtractedField], chunks: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=iso(document.created_at),
        chunks=chunks,
        fields=[_field_out(field) for field in fields],
    )


async def _load_document(document_id: str, user: TokenPayload, session: AsyncSession) -> Document:
    document = await session.get(Document, document_id)
    if document is None or document.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/documents", response_model=DocumentOut)
async def verify_document(
    file: UploadFile,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentOut:
    filename = file.filename or "document.txt"
    if not filename.lower().endswith(_SUPPORTED_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Supported formats: {', '.join(_SUPPORTED_SUFFIXES)}",
        )

    raw = await file.read()
    text = extract_text(filename, raw)
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File is empty")

    document_id = str(uuid.uuid4())
    document = Document(
        id=document_id,
        business_id=user.business_id,
        filename=filename,
        storage_path="verified-inline",
        status="processed",
    )
    session.add(document)

    financial_rows = (await session.execute(
        select(FinancialRecord).where(FinancialRecord.business_id == user.business_id)
    )).scalars().all()
    extracted = cross_check_fields(extract_fields(text), [as_dict(row) for row in financial_rows])

    fields: list[ExtractedField] = []
    for item in extracted:
        field = ExtractedField(
            id=str(uuid.uuid4()),
            business_id=user.business_id,
            document_id=document_id,
            field_name=item["field_name"],
            field_value=item["field_value"],
            confidence=item["confidence"],
            verified=item["verified"],
            period=item["period"],
        )
        session.add(field)
        fields.append(field)

    chunks = chunk_document(text, source=filename)
    vector_store.upsert(chunks)
    await session.commit()
    return _document_out(document, fields, len(chunks))


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    limit: int = 50,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    documents = (await session.execute(
        select(Document)
        .where(Document.business_id == user.business_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )).scalars().all()
    results: list[DocumentOut] = []
    for document in documents:
        fields = (await session.execute(
            select(ExtractedField).where(ExtractedField.document_id == document.id)
        )).scalars().all()
        chunk_count = (await session.execute(
            select(func.count(DocumentChunkRow.id)).where(DocumentChunkRow.document_id == document.id)
        )).scalar_one()
        results.append(_document_out(document, list(fields), chunk_count))
    return results


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    document = await _load_document(document_id, user, session)
    fields = (await session.execute(
        select(ExtractedField).where(ExtractedField.document_id == document_id)
    )).scalars().all()
    return _document_out(document, list(fields), 0)


@router.post("/fields/{field_id}/verify", response_model=ExtractedFieldOut)
async def verify_field(
    field_id: str,
    payload: FieldVerificationIn,
    user: TokenPayload = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExtractedFieldOut:
    field = await session.get(ExtractedField, field_id)
    if field is None or field.business_id != user.business_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted field not found")

    field.verified = payload.verified
    if payload.field_value is not None:
        field.field_value = payload.field_value
    await session.commit()
    await session.refresh(field)
    return _field_out(field)
