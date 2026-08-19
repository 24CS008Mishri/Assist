from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models.schemas import (
    AssistantRequest,
    AssistantResponse,
    DocumentRecord,
    QAResponse,
    QuestionRequest,
    UploadResponse,
)
from backend.services.document_service import delete_document, get_all_documents
from backend.services.pdf_service import extract_text_from_pdf
from backend.services.rag_service import answer_question, process_and_store_pdf


router = APIRouter(tags=["rag"])


@router.get("/rag/documents", response_model=List[DocumentRecord])
@router.get("/api/documents", response_model=List[DocumentRecord])
async def list_documents():
    return get_all_documents()


@router.delete("/rag/documents/{filename}")
@router.delete("/api/documents/{filename}")
async def delete_document_endpoint(filename: str) -> Dict[str, str]:
    if not delete_document(filename):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Successfully deleted {filename}"}


@router.post("/rag/upload", response_model=UploadResponse)
@router.post("/api/documents/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        text = extract_text_from_pdf(await file.read())
        total_chunks, already_indexed = process_and_store_pdf(text, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadResponse(
        filename=file.filename,
        message="PDF already indexed" if already_indexed else "PDF uploaded and indexed successfully",
        total_chunks=total_chunks,
        already_indexed=already_indexed,
    )


@router.post("/rag/ask", response_model=QAResponse)
async def ask_question_endpoint(request: QuestionRequest) -> QAResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        answer, sources = answer_question(query)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QAResponse(query=query, answer=answer, sources=sources)


@router.post("/api/assistant", response_model=AssistantResponse)
async def assistant_endpoint(request: AssistantRequest) -> AssistantResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        answer, sources = answer_question(question, request.history)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AssistantResponse(question=question, answer=answer, sources=sources)
