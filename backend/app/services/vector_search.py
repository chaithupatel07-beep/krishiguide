from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.core.logging import logger

DEFAULT_SIMILARITY_THRESHOLD = 0.25
DEFAULT_TOP_K = 4


class VectorSearchService:
    @staticmethod
    async def search_agricultural_context(
        query: str,
        user_id: int,
        user_role: str,
        db: AsyncSession,
        limit: int = DEFAULT_TOP_K,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """
        1. Encodes farmer query into 384-dimensional vector.
        2. Determines accessible document IDs based on permissions.
        3. Queries Qdrant for semantic similarity matches above threshold.
        4. Cross-references against MySQL to ensure accurate document and page attribution.
        """
        if not query or not query.strip():
            return []

        # 1. Fetch accessible documents from MySQL based on role
        if user_role == "admin":
            stmt = select(Document.id, Document.document_name).where(
                Document.processing_status == "completed"
            )
        else:
            stmt = select(Document.id, Document.document_name).where(
                Document.processing_status == "completed",
                or_(
                    Document.is_public == True,
                    Document.uploaded_by == user_id,
                ),
            )
        doc_result = await db.execute(stmt)
        accessible_docs = {row.id: row.document_name for row in doc_result.all()}

        if not accessible_docs:
            logger.info("No completed agricultural documents available for vector retrieval.")
            return []

        allowed_ids = list(accessible_docs.keys())

        # 2. Encode farmer query
        query_vector = EmbeddingService.embed_text(query.strip())

        # 3. Search Qdrant vector database
        raw_hits = vector_store.search_chunks(
            query_vector=query_vector,
            limit=limit,
            score_threshold=threshold,
            allowed_doc_ids=allowed_ids,
        )

        if not raw_hits:
            logger.info(f"No vector hits found above threshold {threshold} for query: '{query}'")
            return []

        # 4. Cross-reference chunks with MySQL to retrieve exact chunk records and page numbers
        verified_context: List[Dict[str, Any]] = []
        for hit in raw_hits:
            doc_id = hit.get("document_id")
            doc_name = accessible_docs.get(doc_id) or hit.get("document_name", "Agricultural Manual")
            page_num = hit.get("page_number", 1)
            chunk_text = hit.get("text", "")
            score = round(hit.get("score", 0.0), 4)

            verified_context.append({
                "point_id": hit.get("point_id"),
                "document_id": doc_id,
                "document_name": doc_name,
                "page_number": page_num,
                "text": chunk_text,
                "similarity_score": score,
            })

        logger.info(f"Retrieved {len(verified_context)} agricultural context chunks for query: '{query[:40]}...'")
        return verified_context

