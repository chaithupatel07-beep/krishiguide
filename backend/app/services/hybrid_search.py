import math
import re
from typing import List, Dict, Any, Optional, Set
from collections import Counter
from app.core.config import settings
from app.core.logging import logger

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves", "what", "is", "the",
    "best", "for"
}


def tokenize(text: str) -> List[str]:
    """Tokenizes text into lowercase alphanumeric keywords excluding stop words."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


class BM25Scorer:
    """Lightweight in-memory BM25 Okapi implementation for agricultural lexical retrieval."""

    def __init__(self, corpus: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = [len(tokenize(doc)) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lens) / max(self.corpus_size, 1)
        self.doc_freqs: Dict[str, int] = Counter()
        self.doc_token_counts: List[Counter] = []

        for doc in corpus:
            tokens = tokenize(doc)
            counts = Counter(tokens)
            self.doc_token_counts.append(counts)
            for token in counts.keys():
                self.doc_freqs[token] += 1

    def score(self, query: str, doc_idx: int) -> float:
        """Calculates BM25 score for a specific document given a query."""
        if doc_idx >= self.corpus_size:
            return 0.0

        query_tokens = tokenize(query)
        if not query_tokens:
            return 0.0

        doc_len = self.doc_lens[doc_idx]
        counts = self.doc_token_counts[doc_idx]
        score = 0.0

        for token in query_tokens:
            if token not in counts:
                continue

            freq = counts[token]
            df = self.doc_freqs.get(token, 0)
            # Standard Lucene/BM25 IDF formula
            idf = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))
            numerator = freq * (self.k1 + 1.0)
            denominator = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / max(self.avg_doc_len, 1)))
            score += idf * (numerator / denominator)

        return score


class HybridSearchService:
    """
    Combines dense semantic vector search with lexical BM25 keyword matching
    using Reciprocal Rank Fusion (RRF) and weighted linear interpolation.
    """

    @staticmethod
    def combine_results(
        semantic_hits: List[Dict[str, Any]],
        all_candidate_chunks: List[Dict[str, Any]],
        query: str,
        semantic_weight: float = 0.70,
        lexical_weight: float = 0.30,
        top_k: int = 4,
        threshold: float = 0.20,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Takes semantic search hits and candidate chunks, applies BM25 scoring and metadata filtering,
        and computes hybrid rank fusion.
        """
        if not semantic_hits and not all_candidate_chunks:
            return []

        # Map semantic scores by chunk unique identifier (document_id + chunk_index)
        semantic_score_map: Dict[str, float] = {}
        chunk_lookup: Dict[str, Dict[str, Any]] = {}

        for hit in semantic_hits:
            key = f"{hit.get('document_id')}_{hit.get('chunk_index')}"
            semantic_score_map[key] = float(hit.get("score") or hit.get("similarity") or 0.0)
            chunk_lookup[key] = hit

        # Build corpus for BM25
        corpus_items = []
        corpus_keys = []
        for c in all_candidate_chunks:
            key = f"{c.get('document_id')}_{c.get('chunk_index')}"
            text = c.get("chunk_text") or c.get("text", "")
            if text:
                corpus_items.append(text)
                corpus_keys.append(key)
                if key not in chunk_lookup:
                    chunk_lookup[key] = c

        # Compute BM25 scores
        bm25_score_map: Dict[str, float] = {}
        if corpus_items:
            bm25 = BM25Scorer(corpus_items)
            max_bm25 = 0.0001
            raw_scores = []
            for idx in range(len(corpus_items)):
                s = bm25.score(query, idx)
                raw_scores.append(s)
                if s > max_bm25:
                    max_bm25 = s

            # Normalize BM25 scores to [0, 1]
            for idx, key in enumerate(corpus_keys):
                bm25_score_map[key] = min(1.0, raw_scores[idx] / max_bm25)

        # Merge and calculate weighted hybrid scores
        all_keys = set(semantic_score_map.keys()).union(set(bm25_score_map.keys()))
        hybrid_results: List[Dict[str, Any]] = []

        for key in all_keys:
            chunk = chunk_lookup.get(key)
            if not chunk:
                continue

            # Metadata category filtering if specified
            if category_filter:
                doc_cat = (chunk.get("category") or chunk.get("meta_info", {}).get("category", "")).lower()
                if doc_cat and category_filter.lower() not in doc_cat:
                    continue

            sem_score = semantic_score_map.get(key, 0.0)
            lex_score = bm25_score_map.get(key, 0.0)

            # Reciprocal Rank Fusion + Weighted linear score
            combined_score = (semantic_weight * sem_score) + (lexical_weight * lex_score)

            if combined_score >= threshold:
                item = dict(chunk)
                item["score"] = round(combined_score, 4)
                item["semantic_score"] = round(sem_score, 4)
                item["lexical_score"] = round(lex_score, 4)
                hybrid_results.append(item)

        # Sort descending by combined hybrid score
        hybrid_results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"Hybrid search evaluated {len(all_keys)} items, returned top {min(top_k, len(hybrid_results))} results.")
        return hybrid_results[:top_k]

