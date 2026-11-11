from typing import List, Dict, Any, Optional
import uuid
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.config import settings
from app.core.logging import logger
from app.services.embeddings import EMBEDDING_DIM

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ImportError:
    QdrantClient = None
    qmodels = None


class VectorStoreService:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.client = None
        self._memory_vectors: Dict[str, Dict[str, Any]] = {}

        if QdrantClient is not None:
            try:
                self.client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY or None,
                    timeout=1.0,
                    check_compatibility=False,
                )
                self._ensure_collection()
            except Exception as e:
                logger.info(f"Qdrant server unavailable ({e}). Initializing embedded vector memory store.")
                try:
                    self.client = QdrantClient(":memory:")
                    self._ensure_collection()
                except Exception as inner_e:
                    logger.warning(f"In-memory Qdrant init failed: {inner_e}. Using Python cosine engine.")
                    self.client = None

    def _ensure_collection(self) -> None:
        """Ensures the vector collection exists in Qdrant with 384 dimensions and Cosine distance."""
        if not self.client or not qmodels:
            return
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"Creating vector collection '{self.collection_name}' (dim={EMBEDDING_DIM})...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=EMBEDDING_DIM,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
        except Exception as e:
            logger.warning(f"Error ensuring Qdrant collection: {e}")

    def delete_document_vectors(self, document_id: int) -> None:
        """Deletes vectors for a document from memory cache and Qdrant."""
        to_del = [
            pid for pid, d in self._memory_vectors.items()
            if d.get("payload", {}).get("document_id") == document_id
        ]
        for pid in to_del:
            self._memory_vectors.pop(pid, None)

        if self.client and qmodels:
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=document_id),
                            )
                        ]
                    ),
                )
            except Exception as e:
                logger.debug(f"Failed to delete Qdrant points for doc {document_id}: {e}")

    def upsert_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[str]:
        """
        Upserts chunk vectors and payload.
        Each item has 'vector' (List[float]) and 'payload' (dict).
        Returns list of point IDs.
        """
        if not chunks_data:
            return []

        point_ids = []

        # Store in in-memory dict as guaranteed local fallback
        for item in chunks_data:
            point_id = item.get("point_id") or str(uuid.uuid4())
            point_ids.append(point_id)
            self._memory_vectors[point_id] = {
                "vector": np.array(item["vector"], dtype=np.float32),
                "payload": item["payload"],
            }

        # Also sync to Qdrant if active
        if self.client and qmodels:
            try:
                points = [
                    qmodels.PointStruct(
                        id=pid,
                        vector=item["vector"],
                        payload=item["payload"],
                    )
                    for pid, item in zip(point_ids, chunks_data)
                ]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                )
            except Exception as e:
                logger.warning(f"Could not upsert into Qdrant: {e}. Fallback cache updated.")

        return point_ids

    def search_chunks(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.20,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches Qdrant or memory cache for top matching chunks given a query vector.
        """
        # Try Qdrant if active
        if self.client and qmodels:
            try:
                filter_query = None
                if allowed_doc_ids is not None:
                    filter_query = qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=doc_id),
                            )
                            for doc_id in allowed_doc_ids
                        ]
                    )

                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=filter_query,
                )

                scored_chunks = []
                for point in results.points:
                    scored_chunks.append({
                        "point_id": point.id,
                        "score": point.score,
                        "document_id": point.payload.get("document_id"),
                        "chunk_id": point.payload.get("chunk_id"),
                        "chunk_index": point.payload.get("chunk_index"),
                        "page_number": point.payload.get("page_number", 1),
                        "text": point.payload.get("text") or point.payload.get("chunk_text") or "",
                        "document_name": point.payload.get("document_name", "Agricultural Manual"),
                    })
                if scored_chunks:
                    return scored_chunks
            except Exception as e:
                logger.debug(f"Qdrant query failed: {e}. Using local vector search.")

        # In-memory cosine search fallback
        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        scored = []
        for pid, data in self._memory_vectors.items():
            payload = data["payload"]
            doc_id = payload.get("document_id")
            if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                continue

            v = data["vector"]
            v_norm = np.linalg.norm(v)
            if v_norm == 0:
                continue
            cos_sim = float(np.dot(q_vec, v) / (q_norm * v_norm))
            if cos_sim >= score_threshold:
                scored.append({
                    "point_id": pid,
                    "score": cos_sim,
                    "document_id": doc_id,
                    "chunk_id": payload.get("chunk_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "page_number": payload.get("page_number", 1),
                    "text": payload.get("text") or payload.get("chunk_text") or "",
                    "document_name": payload.get("document_name", "Agricultural Manual"),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def search_pgvector(
        self,
        db: AsyncSession,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.20,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Direct pgvector SQL similarity search on PostgreSQL document_chunks table:
        SELECT ... ORDER BY embedding <=> '[...]'
        Falls back seamlessly to search_chunks if pgvector is not configured or query fails.
        """
        try:
            from app.models.document import Document, DocumentChunk
            # Check if current DB dialect is PostgreSQL
            bind = db.get_bind()
            dialect = bind.dialect.name if hasattr(bind, "dialect") else ""

            if dialect == "postgresql":
                # Check pgvector cosine distance
                str_vec = "[" + ",".join(str(f) for f in query_vector) + "]"
                doc_filter = ""
                params = {"qvec": str_vec, "limit": limit}
                if allowed_doc_ids:
                    doc_filter = "AND c.document_id = ANY(:allowed_ids)"
                    params["allowed_ids"] = allowed_doc_ids

                sql = text(f"""
                    SELECT c.id, c.document_id, c.chunk_index, c.chunk_text, c.page_number,
                           d.document_name,
                           1 - (c.embedding <=> :qvec) AS similarity
                    FROM document_chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.embedding IS NOT NULL {doc_filter}
                    ORDER BY c.embedding <=> :qvec
                    LIMIT :limit
                """)
                res = await db.execute(sql, params)
                rows = res.mappings().all()
                results = []
                for r in rows:
                    sim = float(r["similarity"]) if r["similarity"] is not None else 0.0
                    if sim >= score_threshold:
                        results.append({
                            "chunk_id": r["id"],
                            "document_id": r["document_id"],
                            "chunk_index": r["chunk_index"],
                            "page_number": r["page_number"],
                            "text": r["chunk_text"],
                            "document_name": r["document_name"],
                            "score": sim,
                        })
                if results:
                    return results
        except Exception as e:
            logger.info(f"pgvector query bypass ({e}), falling back to vector store service.")

        return self.search_chunks(
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            allowed_doc_ids=allowed_doc_ids,
        )


vector_store = VectorStoreService()
