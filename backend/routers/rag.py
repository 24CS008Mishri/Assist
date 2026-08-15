from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models.schemas import QAResponse, QuestionRequest, UploadResponse
from backend.services.pdf_service import extract_text_from_pdf
from backend.services.rag_service import process_and_store_pdf , answer_question

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()

    try:
        text = extract_text_from_pdf(file_bytes)
        total_chunks = process_and_store_pdf(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadResponse(
        filename=file.filename,
        message="PDF uploaded and indexed successfully",
        total_chunks=total_chunks,
    )


@router.post("/ask", response_model=QAResponse)
async def ask_question(request: QuestionRequest) -> QAResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        answer = answer_question(request.query)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QAResponse(query=request.query, answer=answer)
