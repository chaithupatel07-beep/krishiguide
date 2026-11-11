import asyncio
from pathlib import Path
from typing import Optional
from sqlalchemy import select, delete
from app.database.connection import AsyncSessionLocal
from app.models.document import Document, DocumentChunk
from app.services.pdf_extractor import extract_pdf_pages
from app.services.docx_extractor import extract_docx_pages
from app.services.txt_extractor import extract_txt_pages
from app.services.chunking import create_document_chunks
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.core.logging import logger


async def ingest_document(document_id: int) -> bool:
    """
    Background worker that ingests an agricultural document (.pdf, .docx, .txt):
    1. Extracts text preserving page/section numbers
    2. Chunks text with overlap
    3. Generates 384-d embeddings using all-MiniLM-L6-v2
    4. Populates pgvector column in document_chunks
    5. Indexes vectors into VectorStore (pgvector / Qdrant / memory)
    6. Updates status to completed or failed
    """
    logger.info(f"Starting background ingestion for document ID: {document_id}")
    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if not doc:
            logger.error(f"Document ID {document_id} not found for background ingestion.")
            return False

        doc.processing_status = "processing"
        doc.processing_error = None
        await session.commit()

        try:
            file_ext = Path(doc.file_path).suffix.lower()

            # 1. Extract pages based on format
            if file_ext == ".pdf":
                pages = await asyncio.to_thread(extract_pdf_pages, doc.file_path)
            elif file_ext in (".docx", ".doc"):
                pages = await asyncio.to_thread(extract_docx_pages, doc.file_path)
            elif file_ext in (".txt", ".md", ".csv"):
                pages = await asyncio.to_thread(extract_txt_pages, doc.file_path)
            else:
                # Default to PDF parser if unknown
                pages = await asyncio.to_thread(extract_pdf_pages, doc.file_path)

            if not pages:
                raise ValueError(f"Document contains no extractable text from format '{file_ext}'.")

            # 2. Chunk text with overlap (500 chars with 100 overlap)
            chunks = create_document_chunks(pages, chunk_size=500, chunk_overlap=100)
            if not chunks:
                raise ValueError("Could not generate valid text chunks from document.")

            # 3. Generate embeddings
            texts = [c["chunk_text"] for c in chunks]
            embeddings = await asyncio.to_thread(EmbeddingService.embed_batch, texts)

            # 4. Clear any previous vectors and DB chunks (for clean re-processing)
            vector_store.delete_document_vectors(doc.id)
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )

            # 5. Prepare vector store payload & upsert
            vector_items = []
            for i, chunk in enumerate(chunks):
                vector_items.append({
                    "vector": embeddings[i],
                    "payload": {
                        "document_id": doc.id,
                        "document_name": doc.document_name,
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "chunk_text": chunk["chunk_text"],
                        "text": chunk["chunk_text"],
                        "uploaded_by": doc.uploaded_by,
                        "is_public": doc.is_public,
                    },
                })

            point_ids = await asyncio.to_thread(vector_store.upsert_chunks, vector_items)

            # 6. Store chunks in database with pgvector embedding
            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["chunk_text"],
                    page_number=chunk["page_number"],
                    meta_info=chunk["meta_info"],
                    vector_reference=point_ids[i] if i < len(point_ids) else None,
                    embedding=embeddings[i] if i < len(embeddings) else None,
                )
                session.add(db_chunk)

            # 7. Update document status
            doc.processing_status = "completed"
            doc.processing_error = None
            doc.meta_info = {
                "total_pages": len(pages),
                "total_chunks": len(chunks),
                "file_type": file_ext,
            }
            await session.commit()
            logger.info(f"Document ID {doc.id} ('{doc.document_name}') ingestion COMPLETED ({len(chunks)} chunks).")
            return True

        except Exception as e:
            logger.error(f"Document ingestion FAILED for ID {doc.id}: {e}", exc_info=True)
            doc.processing_status = "failed"
            doc.processing_error = str(e)
            await session.commit()
            return False
