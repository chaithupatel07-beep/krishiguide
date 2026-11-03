from typing import List, Dict, Any
import re


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    Splits text into overlapping chunks of approximately chunk_size characters,
    prioritizing clean sentence or paragraph boundaries.
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    # Split into paragraphs/sentences first
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(current_chunk) + len(sentence) + 1 <= chunk_size:
            current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
                # Keep overlap from the end of current_chunk
                if len(current_chunk) > chunk_overlap:
                    overlap_seed = current_chunk[-chunk_overlap:]
                    # Try to break at word boundary
                    last_space = overlap_seed.find(" ")
                    if last_space != -1:
                        overlap_seed = overlap_seed[last_space + 1 :]
                    current_chunk = f"{overlap_seed} {sentence}".strip()
                else:
                    current_chunk = sentence
            else:
                # A single sentence longer than chunk_size: hard split
                for i in range(0, len(sentence), chunk_size - chunk_overlap):
                    chunks.append(sentence[i : i + chunk_size])
                current_chunk = ""

    if current_chunk and current_chunk not in chunks:
        chunks.append(current_chunk)

    return [c.strip() for c in chunks if len(c.strip()) > 10]


def create_document_chunks(
    pages: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Creates overlapping chunks across extracted PDF pages, tracking 1-indexed page numbers.
    """
    all_chunks: List[Dict[str, Any]] = []
    global_index = 0

    for page_data in pages:
        page_num = page_data["page_number"]
        page_text = page_data["text"]
        page_chunks = split_text_into_chunks(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_text in page_chunks:
            all_chunks.append({
                "chunk_index": global_index,
                "chunk_text": chunk_text,
                "page_number": page_num,
                "meta_info": {
                    "page": page_num,
                    "char_count": len(chunk_text),
                },
            })
            global_index += 1

    return all_chunks

