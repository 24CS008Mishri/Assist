import pymupdf


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if not file_bytes:
        raise ValueError("PDF content is empty")

    with pymupdf.open(stream=file_bytes, filetype="pdf") as document:
        pages = []
        for page_number, page in enumerate(document, start=1):
            text = (page.get_text() or "").strip()
            if text:
                pages.append(f"Page {page_number}\n{text}")

    extracted = "\n\n".join(pages).strip()
    if not extracted:
        raise ValueError("No readable text was found in the PDF")
    return extracted
