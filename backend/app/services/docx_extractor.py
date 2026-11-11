from typing import List, Dict, Any
import re
from pathlib import Path
from app.core.logging import logger

try:
    import docx
except ImportError:
    docx = None


def clean_text(text: str) -> str:
    """Removes redundant whitespace, non-printable characters, and blank lines."""
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_docx_pages(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text paragraph-by-paragraph or by page-breaks from a DOCX document.
    Returns a list of dictionaries with pseudo-page numbers and sanitized text.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"DOCX file not found at: {file_path}")

    if docx is None:
        raise RuntimeError("python-docx is not installed in the Python environment.")

    logger.info(f"Extracting text from DOCX: {path.name}")
    pages: List[Dict[str, Any]] = []

    try:
        doc = docx.Document(str(path))
        current_page_text = []
        page_num = 1
        current_len = 0

        for para in doc.paragraphs:
            p_text = clean_text(para.text)
            if not p_text:
                continue

            current_page_text.append(p_text)
            current_len += len(p_text)

            # Paginate roughly every ~1500 chars if no explicit page breaks
            if current_len >= 1500:
                combined = "\n\n".join(current_page_text)
                pages.append({
                    "page_number": page_num,
                    "text": combined,
                    "char_count": len(combined),
                })
                page_num += 1
                current_page_text = []
                current_len = 0

        # Remaining text
        if current_page_text:
            combined = "\n\n".join(current_page_text)
            pages.append({
                "page_number": page_num,
                "text": combined,
                "char_count": len(combined),
            })

        # Also extract table text if present
        for table in doc.tables:
            table_lines = []
            for row in table.rows:
                row_cells = [clean_text(cell.text) for cell in row.cells if clean_text(cell.text)]
                if row_cells:
                    table_lines.append(" | ".join(row_cells))
            if table_lines:
                combined = "\n".join(table_lines)
                pages.append({
                    "page_number": page_num,
                    "text": f"Table data:\n{combined}",
                    "char_count": len(combined),
                })
                page_num += 1

    except Exception as e:
        logger.error(f"Failed to extract text from DOCX {path.name}: {e}")
        raise RuntimeError(f"Error parsing DOCX file '{path.name}': {str(e)}") from e

    logger.info(f"Successfully extracted {len(pages)} sections from {path.name}")
    return pages
