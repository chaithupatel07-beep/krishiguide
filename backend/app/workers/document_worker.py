import asyncio
from typing import Optional
from sqlalchemy import select, delete
from app.database.connection import AsyncSessionLocal
from app.models.document import Document, DocumentChunk
from app.services.pdf_extractor import extract_pdf_pages
from app.services.chunking import create_document_chunks
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.core.logging import logger


async def ingest_document(document_id: int) -> bool:
    """
    Background worker that ingests an agricultural PDF:
    1. Extracts text preserving page numbers with PyMuPDF
    2. Chunks text with overlap
    3. Generates 384-d embeddings using all-MiniLM-L6-v2
    4. Indexes vectors into Qdrant
    5. Stores chunk records and metadata in MySQL
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
            # 1. Extract PDF pages
            pages = await asyncio.to_thread(extract_pdf_pages, doc.file_path)
            if not pages:
                raise ValueError("PDF document contains no extractable text.")

            # 2. Chunk text with overlap
            chunks = create_document_chunks(pages, chunk_size=500, chunk_overlap=100)
            if not chunks:
                raise ValueError("Could not generate valid text chunks from document.")

            # 3. Generate embeddings
            texts = [c["chunk_text"] for c in chunks]
            embeddings = await asyncio.to_thread(EmbeddingService.embed_batch, texts)

            # 4. Clear any previous vectors and DB chunks (for clean retries)
            vector_store.delete_document_vectors(doc.id)
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )

            # 5. Prepare Qdrant payload & upsert
            qdrant_items = []
            for i, chunk in enumerate(chunks):
                qdrant_items.append({
                    "vector": embeddings[i],
                    "payload": {
                        "document_id": doc.id,
                        "document_name": doc.document_name,
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "chunk_text": chunk["chunk_text"],
                        "uploaded_by": doc.uploaded_by,
                        "is_public": doc.is_public,
                    },
                })

            point_ids = await asyncio.to_thread(vector_store.upsert_chunks, qdrant_items)

            # 6. Store chunks in MySQL
            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["chunk_text"],
                    page_number=chunk["page_number"],
                    meta_info=chunk["meta_info"],
                    vector_reference=point_ids[i] if i < len(point_ids) else None,
                )
                session.add(db_chunk)

            # 7. Update document status
            doc.processing_status = "completed"
            doc.processing_error = None
            doc.meta_info = {
                "total_pages": len(pages),
                "total_chunks": len(chunks),
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
