from typing import List, Dict, Any
import re
from pathlib import Path
from app.core.logging import logger


def clean_text(text: str) -> str:
    """Removes redundant whitespace, non-printable characters, and blank lines."""
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_txt_pages(file_path: str) -> List[Dict[str, Any]]:
    """
    Reads plain text from .txt file using UTF-8 or Latin-1 encoding,
    chunking into pseudo-pages for unified chunking and citation.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"TXT file not found at: {file_path}")

    logger.info(f"Extracting text from TXT: {path.name}")
    raw_content = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw_content = f.read()
            break
        except UnicodeDecodeError:
            continue

    sanitized = clean_text(raw_content)
    if not sanitized:
        return []

    # Break into page-like segments of ~1500 chars to enable page citations
    pages: List[Dict[str, Any]] = []
    paragraphs = sanitized.split("\n\n")
    current_page = []
    page_num = 1
    current_len = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        current_page.append(p)
        current_len += len(p)
        if current_len >= 1500:
            text_block = "\n\n".join(current_page)
            pages.append({
                "page_number": page_num,
                "text": text_block,
                "char_count": len(text_block),
            })
            page_num += 1
            current_page = []
            current_len = 0

    if current_page:
        text_block = "\n\n".join(current_page)
        pages.append({
            "page_number": page_num,
            "text": text_block,
            "char_count": len(text_block),
        })

    logger.info(f"Successfully extracted {len(pages)} sections from {path.name}")
    return pages
