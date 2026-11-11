from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.core.logging import logger

DEFAULT_SIMILARITY_THRESHOLD = 0.20
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
        3. Queries pgvector or vector store for semantic similarity matches above threshold.
        4. Cross-references against database to ensure accurate document and page attribution.
        """
        if not query or not query.strip():
            return []

        # 1. Fetch accessible documents based on role
        allowed_ids = []
        accessible_docs = {}
        try:
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
            rows = doc_result.all()
            accessible_docs = {row.id: row.document_name for row in rows}
            allowed_ids = list(accessible_docs.keys())
        except Exception as e:
            logger.warning(f"Could not load documents from DB: {e}. Searching all indexed memory.")
            allowed_ids = None

        # 2. Encode farmer query
        query_vector = EmbeddingService.embed_text(query.strip())

        # 3. Search pgvector / vector store
        results = await vector_store.search_pgvector(
            db=db,
            query_vector=query_vector,
            limit=limit,
            score_threshold=threshold,
            allowed_doc_ids=allowed_ids if allowed_ids else None,
        )

        # 4. If DB documents are mapped, ensure document names are accurate
        for item in results:
            doc_id = item.get("document_id")
            if doc_id and doc_id in accessible_docs:
                item["document_name"] = accessible_docs[doc_id]

        logger.info(f"Vector search retrieved {len(results)} chunks for query: '{query[:40]}'")
        return results
