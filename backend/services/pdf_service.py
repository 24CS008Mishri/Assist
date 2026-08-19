from dataclasses import dataclass
from typing import List

import pymupdf


@dataclass(frozen=True)
class PdfPage:
    page_number: int
    text: str


def extract_pages_from_pdf(file_bytes: bytes) -> List[PdfPage]:
    if not file_bytes:
        raise ValueError("PDF content is empty")

    with pymupdf.open(stream=file_bytes, filetype="pdf") as document:
        pages = []
        for page_number, page in enumerate(document, start=1):
            text = (page.get_text() or "").strip()
            if text:
                pages.append(PdfPage(page_number=page_number, text=text))

    if not pages:
        raise ValueError("No readable text was found in the PDF")
    return pages


def combine_pdf_pages(pages: List[PdfPage]) -> str:
    return "\n\n".join(
        f"Page {page.page_number}\n{page.text}" for page in pages
    ).strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Backward-compatible flattened PDF text extraction."""
    return combine_pdf_pages(extract_pages_from_pdf(file_bytes))
