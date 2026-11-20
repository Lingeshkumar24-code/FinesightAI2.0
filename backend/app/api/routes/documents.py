"""Tenant-scoped document upload and RAG indexing."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_vector_store
from app.config import Settings, get_settings
from app.core.security import TokenPayload, get_current_user
from app.db.models import Document, DocumentChunkRow
from app.db.session import get_session
from app.models.schemas import DocumentUploadResponse
from app.rag.ingestion import chunk_document
from app.rag.vectorstore import VectorStore
from app.services.document_extraction import extract_document

router = APIRouter(prefix="/documents", tags=["documents"])

_SUPPORTED_SUFFIXES = (".txt", ".csv", ".md", ".xlsx", ".xlsm", ".xltx", ".xltm", ".xls", ".pdf", ".docx")


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    user: TokenPayload = Depends(get_current_user),
    vector_store: VectorStore = Depends(get_vector_store),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    filename = (file.filename or "upload.txt").replace("\\", "/").split("/")[-1]
    lower_name = filename.lower()
    if not lower_name.endswith(_SUPPORTED_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Supported formats: {', '.join(_SUPPORTED_SUFFIXES)}.",
        )

    raw = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )

    extracted = extract_document(filename, raw)
    if not extracted.text.strip():
        detail = "File contains no extractable text. " + " ".join(extracted.warnings)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    document_id = str(uuid.uuid4())
    chunks = chunk_document(
        extracted.text,
        source=filename,
        metadata={
            "business_id": user.business_id,
            "document_id": document_id,
            "filename": filename,
            **extracted.metadata,
        },
    )

    # Persist metadata and chunks before indexing. If the DB write fails, the
    # vector store is not updated with evidence the application cannot track.
    document = Document(
        id=document_id,
        business_id=user.business_id,
        filename=filename,
        status="processed",
    )
    session.add(document)
    if chunks:
        await session.execute(
            insert(DocumentChunkRow),
            [
                {
                    "id": chunk.id,
                    "document_id": document_id,
                    "chunk_index": int(chunk.metadata["chunk_index"]),
                    "text": chunk.text,
                    "source_location": str(chunk.metadata.get("source_location", "")),
                }
                for chunk in chunks
            ],
        )
    await session.commit()
    vector_store.upsert(chunks)

    return DocumentUploadResponse(
        document_id=document_id,
        source=filename,
        chunks_indexed=len(chunks),
    )
