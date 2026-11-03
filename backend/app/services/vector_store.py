from typing import List, Dict, Any, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.core.config import settings
from app.core.logging import logger
from app.services.embeddings import EMBEDDING_DIM


class VectorStoreService:
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        try:
            self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
            self._ensure_collection()
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant at {settings.QDRANT_URL}: {e}. Falling back to in-memory Qdrant client.")
            self.client = QdrantClient(":memory:")
            self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensures the vector collection exists in Qdrant with 384 dimensions and Cosine distance."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection '{self.collection_name}' (dim={EMBEDDING_DIM})...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=EMBEDDING_DIM,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {e}")

    def upsert_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[str]:
        """
        Upserts chunk vectors and payload into Qdrant.
        Each item in chunks_data must have 'vector' (List[float]) and 'payload' (dict).
        Returns list of point IDs.
        """
        if not chunks_data:
            return []

        points = []
        point_ids = []

        for item in chunks_data:
            point_id = item.get("point_id") or str(uuid.uuid4())
            point_ids.append(point_id)
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=item["vector"],
                    payload=item["payload"],
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info(f"Upserted {len(points)} vector points into Qdrant collection '{self.collection_name}'.")
        return point_ids

    def search_chunks(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.25,
        allowed_doc_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches Qdrant for top matching chunks given a query vector.
        """
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
                "point_id": str(point.id),
                "score": float(point.score),
                "payload": point.payload or {},
                "text": (point.payload or {}).get("chunk_text", ""),
                "document_id": (point.payload or {}).get("document_id"),
                "document_name": (point.payload or {}).get("document_name", ""),
                "page_number": (point.payload or {}).get("page_number", 1),
            })

        return scored_chunks

    def delete_document_vectors(self, document_id: int) -> None:
        """Deletes all vector points associated with a specific document_id."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )
            logger.info(f"Deleted vector points for document ID {document_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for document {document_id}: {e}")


# Singleton instance
vector_store = VectorStoreService()

