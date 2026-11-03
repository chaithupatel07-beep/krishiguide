from typing import List, Optional, Any
import numpy as np
from app.core.logging import logger

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

_model_instance: Optional[Any] = None
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def get_embedding_model():
    """Lazy loader for the Sentence Transformers model."""
    global _model_instance
    if _model_instance is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed.")
        logger.info(f"Loading SentenceTransformer model: {MODEL_NAME}...")
        _model_instance = SentenceTransformer(MODEL_NAME)
        logger.info("SentenceTransformer model loaded successfully.")
    return _model_instance


class EmbeddingService:
    @staticmethod
    def embed_text(text: str) -> List[float]:
        """Generates a 384-dimensional normalized embedding for a single string."""
        if not text:
            return [0.0] * EMBEDDING_DIM
        model = get_embedding_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)

    @staticmethod
    def embed_batch(texts: List[str]) -> List[List[float]]:
        """Generates normalized embeddings for a batch of strings."""
        if not texts:
            return []
        model = get_embedding_model()
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vecs.tolist() if hasattr(vecs, "tolist") else [list(v) for v in vecs]
