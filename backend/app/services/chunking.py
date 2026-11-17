import hashlib
import re
from typing import List, Dict, Any, Optional, Set
from app.core.config import settings
from app.core.logging import logger

# Regex to detect and neutralize potential prompt injection instructions in uploaded documents
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*\|?im_start\|?\s*>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(safety|security|rules)", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """
    Cleans raw document text:
    - Removes non-printable/control characters while preserving unicode and formatting.
    - Normalizes excessive whitespace and newlines.
    - Disarms prompt injection delimiters so uploaded text is treated purely as untrusted data.
    """
    if not text:
        return ""

    # Remove non-printable control characters (except newline, tab, carriage return)
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t\r")

    # Neutralize prompt injection attempts in documents
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[FILTERED_INSTRUCTION]", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


def calculate_chunk_hash(text: str) -> str:
    """Computes SHA256 hex digest of normalized chunk text."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_jaccard_similarity(text1: str, text2: str) -> float:
    """Calculates word-level Jaccard similarity for near-duplicate detection."""
    set1 = set(text1.lower().split())
    set2 = set(text2.lower().split())
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def split_text_into_chunks(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[str]:
    """
    Splits text into overlapping chunks, prioritizing sentence/paragraph boundaries.
    Defaults to settings.RAG_CHUNK_SIZE and settings.RAG_CHUNK_OVERLAP.
    """
    size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP

    sanitized = sanitize_text(text)
    if not sanitized:
        return []

    if len(sanitized) <= size:
        return [sanitized]

    # Sentence boundary split
    sentences = re.split(r"(?<=[.!?\n])\s+", sanitized)
    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(current_chunk) + len(sentence) + 1 <= size:
            current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
                if len(current_chunk) > overlap:
                    overlap_seed = current_chunk[-overlap:]
                    last_space = overlap_seed.find(" ")
                    if last_space != -1:
                        overlap_seed = overlap_seed[last_space + 1 :]
                    current_chunk = f"{overlap_seed} {sentence}".strip()
                else:
                    current_chunk = sentence
            else:
                for i in range(0, len(sentence), size - overlap):
                    chunks.append(sentence[i : i + size])
                current_chunk = ""

    if current_chunk and current_chunk not in chunks:
        chunks.append(current_chunk)

    return [c.strip() for c in chunks if len(c.strip()) > 10]


def deduplicate_chunks(chunks: List[Dict[str, Any]], near_dup_threshold: float = 0.92) -> List[Dict[str, Any]]:
    """
    Removes exact duplicate chunks (e.g. repeated page headers/footers) and near-duplicates (>92% similarity).
    Preserves order and page traceability.
    """
    if not settings.RAG_DEDUPLICATION_ENABLED or not chunks:
        return chunks

    unique_chunks: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()

    for chunk in chunks:
        c_hash = chunk.get("hash") or calculate_chunk_hash(chunk["chunk_text"])
        if c_hash in seen_hashes:
            continue

        # Check near-duplicates against recent unique chunks
        is_near_dup = False
        chunk_text = chunk["chunk_text"]
        for prev in unique_chunks[-10:]:
            if compute_jaccard_similarity(chunk_text, prev["chunk_text"]) >= near_dup_threshold:
                is_near_dup = True
                break

        if not is_near_dup:
            seen_hashes.add(c_hash)
            chunk["hash"] = c_hash
            unique_chunks.append(chunk)

    if len(unique_chunks) < len(chunks):
        logger.info(f"Deduplication removed {len(chunks) - len(unique_chunks)} redundant chunks.")

    return unique_chunks


def create_document_chunks(
    pages: List[Dict[str, Any]],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    document_name: str = "Agricultural Document",
) -> List[Dict[str, Any]]:
    """
    Creates sanitized, deduplicated overlapping chunks across pages with 1-indexed page tracking.
    """
    raw_chunks: List[Dict[str, Any]] = []
    global_index = 0

    for page_data in pages:
        if isinstance(page_data, (tuple, list)):
            page_num = page_data[0] if len(page_data) > 0 else 1
            page_text = page_data[1] if len(page_data) > 1 else ""
        elif isinstance(page_data, dict):
            page_num = page_data.get("page_number", 1)
            page_text = page_data.get("text", "")
        else:
            page_num = 1
            page_text = str(page_data)
        page_chunks = split_text_into_chunks(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_text in page_chunks:
            c_hash = calculate_chunk_hash(chunk_text)
            raw_chunks.append({
                "chunk_index": global_index,
                "chunk_text": chunk_text,
                "text": chunk_text,
                "page_number": page_num,
                "hash": c_hash,
                "meta_info": {
                    "page": page_num,
                    "char_count": len(chunk_text),
                    "word_count": len(chunk_text.split()),
                    "document_name": document_name,
                },
            })
            global_index += 1

    # Apply intelligent deduplication
    deduped = deduplicate_chunks(raw_chunks)

    # Re-index chunks consecutively
    for i, c in enumerate(deduped):
        c["chunk_index"] = i

    return deduped
