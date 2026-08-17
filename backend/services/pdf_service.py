import pymupdf

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from PDF file bytes."""
    if not file_bytes:
        raise ValueError("PDF content is empty")

    # Open PDF from bytes stream
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    text_parts = []

    for page in doc:
        page_text = page.get_text() or ""
        if page_text.strip():
            text_parts.append(page_text)

    return "\n\n".join(text_parts)