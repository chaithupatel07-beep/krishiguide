from typing import List, Dict, Any
import re
from pathlib import Path
from app.core.logging import logger

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


def clean_text(text: str) -> str:
    """Removes redundant whitespace, non-printable characters, and blank lines."""
    if not text:
        return ""
    # Normalize unicode whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Remove excessive consecutive newlines
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_pdf_pages(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from an agricultural PDF document using PyMuPDF.
    Returns a list of dictionaries with page numbers (1-indexed) and sanitized text.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed in the Python environment.")

    logger.info(f"Extracting text from PDF: {path.name}")
    pages: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(str(path))
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            raw_text = page.get_text("text") or ""
            sanitized = clean_text(raw_text)
            if sanitized:
                pages.append({
                    "page_number": page_idx + 1,
                    "text": sanitized,
                    "char_count": len(sanitized),
                })
        doc.close()
    except Exception as e:
        logger.error(f"Failed to extract text from {path.name}: {e}")
        raise RuntimeError(f"Error parsing PDF file '{path.name}': {str(e)}") from e

    logger.info(f"Successfully extracted {len(pages)} pages with text from {path.name}")
    return pages
