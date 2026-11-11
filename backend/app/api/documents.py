import os
import re
import uuid
from typing import List, Optional
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    status,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database.connection import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentResponse, DocumentProcessResponse
from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.logging import logger
from app.workers.document_worker import ingest_document
from app.services.vector_store import vector_store

router = APIRouter(prefix="/documents", tags=["Documents & Ingestion"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


def sanitize_filename(filename: str) -> str:
    """Strips path traversal sequences and dangerous characters."""
    clean = Path(filename).name
    clean = re.sub(r"[^\w\s.-]", "", clean).strip()
    return clean or "document.pdf"


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an agricultural document (PDF, DOCX, TXT)",
    description="Uploads a PDF, DOCX, or TXT file, stores it securely, creates a database record, and queues ingestion.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Agricultural document to ingest"),
    is_public: bool = Form(True, description="Whether document is public or private"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Validate file extension
    original_name = file.filename or "uploaded_document.pdf"
    file_ext = Path(original_name).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format '{file_ext}'. Supported formats: PDF, DOCX, DOC, TXT.",
        )

    # 3. Read content and check size limit
    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty (0 bytes).",
        )
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 25MB (Received {file_size / (1024*1024):.2f}MB).",
        )

    # 4. Generate safe unique filename to prevent path traversal and collisions
    clean_name = sanitize_filename(original_name)
    unique_filename = f"{uuid.uuid4().hex}_{clean_name}"
    save_path = Path(settings.UPLOAD_DIR) / unique_filename

    # Save to disk
    with open(save_path, "wb") as f:
        f.write(content)

    # 5. Determine public/private scope (only admin can publish system-wide public docs; farmers upload private docs)
    effective_is_public = is_public if current_user.role == "admin" else False

    # 6. Create Document record in MySQL
    doc = Document(
        document_name=clean_name,
        file_path=str(save_path),
        file_type=file.content_type or f"application/{file_ext.lstrip('.')}",
        file_size=file_size,
        uploaded_by=current_user.id,
        is_public=effective_is_public,
        processing_status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(f"User {current_user.email} uploaded document ID {doc.id} ('{clean_name}')")

    # 7. Queue background ingestion (does not block HTTP response)
    background_tasks.add_task(ingest_document, doc.id)

    res = DocumentResponse.model_validate(doc)
    res.total_chunks = 0
    return res


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List accessible agricultural documents",
    description="Returns public documents and user-owned private documents.",
)
async def list_documents(
    processing_status: Optional[str] = Query(None, description="Filter by status: pending, processing, completed, failed"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Document)

    # Role-based visibility:
    # Admins see all documents; farmers and experts see public docs + their own uploads
    if current_user.role != "admin":
        query = query.where(
            or_(
                Document.is_public == True,
                Document.uploaded_by == current_user.id,
            )
        )

    if processing_status:
        query = query.where(Document.processing_status == processing_status)

    query = query.order_by(Document.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    docs = result.scalars().all()

    # Annotate total chunks
    response_list = []
    for doc in docs:
        chunk_count_result = await db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
        )
        total_chunks = chunk_count_result.scalar_one() or 0
        doc_res = DocumentResponse.model_validate(doc)
        doc_res.total_chunks = total_chunks
        response_list.append(doc_res)

    return response_list


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details by ID",
)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Verify visibility: public or owned by user or admin
    if not doc.is_public and doc.uploaded_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view this private document.",
        )

    chunk_count_result = await db.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    )
    total_chunks = chunk_count_result.scalar_one() or 0
    res = DocumentResponse.model_validate(doc)
    res.total_chunks = total_chunks
    return res


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document and its vector embeddings",
)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Authorization: only admin or the user who uploaded can delete
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to delete this document.",
        )

    # 1. Delete vectors from Qdrant
    vector_store.delete_document_vectors(doc.id)

    # 2. Delete physical file from disk if exists
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as e:
        logger.warning(f"Could not delete file {doc.file_path}: {e}")

    # 3. Delete from MySQL (cascades to document_chunks)
    await db.delete(doc)
    await db.commit()

    logger.info(f"User {current_user.email} deleted document ID {document_id}")
    return {
        "success": True,
        "message": f"Document '{doc.document_name}' and its vector embeddings deleted successfully.",
        "document_id": document_id,
    }


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Trigger or retry document ingestion in background",
)
async def process_document_endpoint(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Authorization: admin or document owner
    if current_user.role != "admin" and doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to trigger processing on this document.",
        )

    # Queue background task
    background_tasks.add_task(ingest_document, doc.id)

    return DocumentProcessResponse(
        document_id=doc.id,
        processing_status="processing",
        message="Document processing queued in background.",
    )

