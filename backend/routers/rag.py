from fastapi import APIRouter, File, HTTPException, UploadFile
from typing import List, Dict, Any

from backend.models.schemas import QAResponse, QuestionRequest, UploadResponse
from backend.services.pdf_service import extract_text_from_pdf
from backend.services.document_service import get_all_documents, delete_document
from backend.services.rag_service import answer_question as generate_answer, process_and_store_pdf


router = APIRouter(prefix="/rag", tags=["rag"])

@router.get("/documents", response_model=List[Dict[str, Any]])
async def list_documents():
    """Returns the list of all indexed documents for the frontend workspace."""
    return get_all_documents()

@router.delete("/documents/{filename}")
async def delete_document_endpoint(filename: str):
    """Deletes a document and its embeddings from MongoDB Atlas."""
    success = delete_document(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Successfully deleted {filename}"}


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()

    try:
        text = extract_text_from_pdf(file_bytes)
        total_chunks = process_and_store_pdf(text,file.filename)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadResponse(
        filename=file.filename,
        message="PDF uploaded and indexed successfully",
        total_chunks=total_chunks,
    )


@router.post("/ask", response_model=QAResponse)
async def ask_question_endpoint(request: QuestionRequest) -> QAResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        answer = generate_answer(request.query)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QAResponse(query=request.query, answer=answer)
