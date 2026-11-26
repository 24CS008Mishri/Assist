from typing import Any, Dict, List, Literal, Optional
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pymongo.errors import PyMongoError

from backend.core.auth import AuthenticatedUser, require_authenticated_user, require_role
from backend.models.schemas import (
    AssistantRequest,
    AssistantResponse,
    DocumentRecord,
    DocumentSourceType,
    QAResponse,
    QuestionRequest,
    UploadResponse,
)
from backend.services.document_service import (
    delete_document,
    generate_document_id,
    get_all_documents,
)
from backend.services.pdf_service import combine_pdf_pages, extract_pages_from_pdf
from backend.services.rag_service import answer_question, process_and_store_pdf
from backend.data.database import get_designer_metadata_collection
from backend.services.workflow_service import (
    actor_record,
    delete_unsubmitted_draft_pdf,
    get_prepared_metadata,
    get_workflow_database,
    read_original_pdf,
    store_original_pdf,
)


router = APIRouter(tags=["rag"])


def _document_scope(user: AuthenticatedUser) -> tuple[str, Optional[str]]:
    if user.role == "admin":
        return DocumentSourceType.AICTE_REFERENCE.value, None
    if user.role == "designer":
        return DocumentSourceType.SUBMITTED_CURRICULUM.value, user.user_id
    require_role(user, "admin", "designer")
    raise AssertionError("require_role always raises for unsupported roles")


@router.get("/rag/documents", response_model=List[DocumentRecord])
@router.get("/api/documents", response_model=List[DocumentRecord])
async def list_documents(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    source_type, owner_id = _document_scope(current_user)
    try:
        return get_all_documents(source_type=source_type, owner_id=owner_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable") from exc


@router.delete("/rag/documents/{filename}")
@router.delete("/api/documents/{filename}")
async def delete_document_endpoint(
    filename: str,
    document_id: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> Dict[str, str]:
    source_type, owner_id = _document_scope(current_user)
    try:
        draft_metadata = None
        if current_user.role == "designer":
            metadata_query = {
                "filename": filename,
                "source_type": source_type,
                "owner_id": owner_id,
                **({"document_id": document_id} if document_id else {}),
            }
            metadata_collection = get_designer_metadata_collection()
            if not document_id and metadata_collection.count_documents(metadata_query) > 1:
                raise HTTPException(status_code=409, detail="More than one version has this filename; refresh and delete the exact version")
            draft_metadata = metadata_collection.find_one(metadata_query)
            if not draft_metadata:
                raise HTTPException(status_code=404, detail="Document not found")
            if draft_metadata.get("handoff_status") == "Ready for institute":
                raise HTTPException(
                    status_code=409,
                    detail="This curriculum has been sent to your Institute Representative and cannot be deleted",
                )
            if get_workflow_database().curriculum_submissions.find_one(
                {"prepared_document_metadata_id": draft_metadata["_id"]},
                {"_id": 1},
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This curriculum is part of submission history and cannot be deleted",
                )
        deleted = delete_document(
            filename,
            source_type=source_type,
            owner_id=owner_id,
            document_id=document_id,
        )
        if deleted and draft_metadata and draft_metadata.get("original_file_id"):
            delete_unsubmitted_draft_pdf(draft_metadata["original_file_id"])
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Successfully deleted {filename}"}


@router.post("/rag/upload", response_model=UploadResponse)
@router.post("/api/documents/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    source_type: DocumentSourceType = Form(DocumentSourceType.AICTE_REFERENCE),
    programme: Literal["B.Tech"] = Form("B.Tech"),
    branch: Literal["CSE"] = Form("CSE"),
    curriculum_id: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    version: Optional[str] = Form(None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    curriculum_id = curriculum_id.strip() if curriculum_id else None
    version = version.strip() if version else None
    if (
        source_type == DocumentSourceType.SUBMITTED_CURRICULUM
        and not curriculum_id
    ):
        raise HTTPException(
            status_code=400,
            detail="curriculum_id is required for submitted curricula",
        )

    if source_type == DocumentSourceType.AICTE_REFERENCE:
        require_role(current_user, "admin")
        owner_id = None
    else:
        require_role(current_user, "designer")
        owner_id = current_user.user_id

    try:
        file_bytes = await file.read(25 * 1024 * 1024 + 1)
        if len(file_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF must be 25 MB or smaller")
        if not file_bytes.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF")
        document_id = generate_document_id(file_bytes)
        pages = extract_pages_from_pdf(file_bytes)
        text = combine_pdf_pages(pages)
        total_chunks, already_indexed = process_and_store_pdf(
            text,
            file.filename,
            pages=pages,
            document_id=document_id,
            source_type=source_type.value,
            programme=programme,
            branch=branch,
            curriculum_id=curriculum_id,
            year=year,
            version=version,
            owner_id=owner_id,
        )
        if source_type == DocumentSourceType.SUBMITTED_CURRICULUM:
            metadata_collection = get_designer_metadata_collection()
            draft = metadata_collection.find_one({
                "document_id": document_id, "source_type": source_type.value, "owner_id": owner_id,
            })
            if not (draft and draft.get("original_file_id")):
                file_id = store_original_pdf(file_bytes, file.filename, {
                    "document_id": document_id,
                    "curriculum_id": curriculum_id,
                    "designer_id": current_user.user_id,
                    "uploaded_by": current_user.user_id,
                    "kind": "designer_draft",
                })
                metadata_collection.update_one(
                    {"document_id": document_id, "source_type": source_type.value, "owner_id": owner_id,
                     "original_file_id": {"$exists": False}},
                    {"$set": {"original_file_id": file_id}},
                )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Document storage is unavailable") from exc

    return UploadResponse(
        filename=file.filename,
        document_id=document_id,
        source_type=source_type,
        programme=programme,
        branch=branch,
        curriculum_id=curriculum_id,
        year=year,
        version=version,
        message="PDF already indexed" if already_indexed else "PDF uploaded and indexed successfully",
        total_chunks=total_chunks,
        already_indexed=already_indexed,
    )


@router.get("/api/documents/{document_id}/original")
def download_original_document(
    document_id: str,
    curriculum_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    if current_user.role == "designer":
        metadata = get_designer_metadata_collection().find_one({
            "source_type": DocumentSourceType.SUBMITTED_CURRICULUM.value,
            "document_id": document_id,
            "curriculum_id": curriculum_id,
            "owner_id": current_user.user_id,
        })
    elif current_user.role == "institute":
        actor = actor_record(current_user.user_id, current_user.role, current_user.name, current_user.email)
        try:
            metadata = get_prepared_metadata(actor, curriculum_id, document_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=403, detail="Draft documents are not available to this role")
    if not metadata or not metadata.get("original_file_id"):
        raise HTTPException(status_code=404, detail="Original draft document not found")
    from bson import ObjectId
    try:
        content, filename = read_original_pdf(ObjectId(str(metadata["original_file_id"])))
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Original draft document not found") from exc
    return StreamingResponse(BytesIO(content), media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, no-store",
    })


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
