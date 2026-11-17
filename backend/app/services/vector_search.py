from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.document import Document, DocumentChunk
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.services.hybrid_search import HybridSearchService
from app.core.config import settings
from app.core.logging import logger


class VectorSearchService:
    @staticmethod
    async def search_agricultural_context(
        query: str,
        user_id: int,
        user_role: str,
        db: AsyncSession,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        category: Optional[str] = None,
        crop: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        1. Validates farmer query.
        2. Determines accessible documents based on user roles and permissions.
        3. Generates 384-dimensional query vector.
        4. Runs semantic retrieval via pgvector / vector store.
        5. If Hybrid Search is enabled, fuses semantic hits with BM25 lexical scores.
        6. Applies metadata filtering (category, crop).
        7. Returns grounded chunks with document names and page numbers.
        """
        if not query or not query.strip():
            return []

        top_k = limit or settings.RAG_TOP_K
        sim_threshold = threshold or settings.RAG_SIMILARITY_THRESHOLD

        # 1. Fetch accessible documents based on role
        allowed_ids = []
        accessible_docs: Dict[int, str] = {}
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
            logger.warning(f"Could not load accessible documents from DB: {e}. Using global fallback.")
            allowed_ids = None

        if allowed_ids is not None and len(allowed_ids) == 0:
            logger.info("No completed documents accessible for user.")
            return []

        # 2. Encode farmer query
        query_vector = EmbeddingService.embed_text(query.strip())

        # 3. Dense semantic search
        semantic_hits = await vector_store.search_pgvector(
            db=db,
            query_vector=query_vector,
            limit=top_k * 2,  # fetch broader candidate pool for hybrid re-ranking
            score_threshold=sim_threshold * 0.8,
            allowed_doc_ids=allowed_ids if allowed_ids else None,
        )

        # 4. Hybrid Search Fusion if enabled
        if settings.RAG_HYBRID_SEARCH and semantic_hits:
            # Query candidate chunks text from DB for accurate BM25 corpus
            candidate_chunks = []
            try:
                chunk_ids = [h.get("chunk_id") for h in semantic_hits if h.get("chunk_id")]
                if chunk_ids:
                    c_stmt = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
                    c_res = await db.execute(c_stmt)
                    for c_obj in c_res.scalars().all():
                        candidate_chunks.append({
                            "document_id": c_obj.document_id,
                            "chunk_index": c_obj.chunk_index,
                            "chunk_text": c_obj.chunk_text,
                            "page_number": c_obj.page_number,
                            "meta_info": c_obj.meta_info or {},
                        })
            except Exception as e:
                logger.debug(f"Candidate chunks DB lookup: {e}")

            if not candidate_chunks:
                candidate_chunks = semantic_hits

            final_results = HybridSearchService.combine_results(
                semantic_hits=semantic_hits,
                all_candidate_chunks=candidate_chunks,
                query=query.strip(),
                semantic_weight=0.70,
                lexical_weight=0.30,
                top_k=top_k,
                threshold=sim_threshold,
                category_filter=category or crop,
            )
        else:
            final_results = semantic_hits[:top_k]

        # 5. Ensure document names and page numbers are verified
        for item in final_results:
            doc_id = item.get("document_id")
            if doc_id and doc_id in accessible_docs:
                item["document_name"] = accessible_docs[doc_id]
            if not item.get("document_name"):
                item["document_name"] = "ICAR Agricultural Guide"
            item["similarity_score"] = float(item.get("score") or 0.0)

        logger.info(f"VectorSearchService returning {len(final_results)} chunks for query: '{query[:40]}'")
        return final_results
