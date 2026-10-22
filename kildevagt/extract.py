"""Turn raw bytes into text. OCR is not done: a PDF without text is reported, not hidden."""
import io
import re

from pypdf import PdfReader


def normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pdf_text(data: bytes) -> tuple[str, int]:
    """Return (text, number of pages). Empty text means the PDF has no text layer (scan)."""
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip(), len(pages)
