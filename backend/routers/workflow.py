from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pymongo.errors import DuplicateKeyError, PyMongoError

from backend.core.auth import AuthenticatedUser, require_authenticated_user, require_role
from backend.models.analyzer_issue_schemas import AnalyzerAnalysis
from backend.models.analyzer_scoring_schemas import AnalyzerScore
from backend.services.analyzer_llm_service import generate_analyzer_issues
from backend.services.curriculum_extraction_service import (
    AmbiguousCurriculumError,
    CurriculumNotFoundError,
    InvalidCurriculumMetadataError,
    extract_structured_curriculum,
)
from backend.services.pdf_service import combine_pdf_pages, extract_pages_from_pdf
from backend.services.rag_service import process_and_store_pdf
from backend.services.scoring_service import score_structured_curriculum
from backend.services.document_service import generate_document_id
from backend.services.aicte_evidence_service import enrich_score_with_aicte_evidence
from backend.services.workflow_service import (
    actor_record,
    analysis_history,
    assign_institution,
    authorize_submission_access,
    create_institution,
    create_institute_user,
    decide_submission,
    fail_submission_upload,
    finalize_submission,
    find_submission,
    handoff_curriculum,
    get_prepared_metadata,
    improvement_history,
    list_institutions,
    list_audit_events,
    get_account_profile,
    list_pending_submissions,
    list_publication_eligible,
    list_published_curricula,
    list_users,
    list_user_notifications,
    mark_all_user_notifications_read,
    mark_user_notification_read,
    prepared_curricula_for_institute,
    read_original_pdf,
    publish_submission,
    record_institute_feedback,
    record_analysis,
    reserve_submission,
    serialize_submission,
    store_original_pdf,
    update_user_access,
    update_account_preferences,
)
from backend.services.change_request_service import (
    list_change_requests,
    update_change_request,
    update_requests_linked_to_submission,
)
from backend.services.decision_support import build_decision_support
from backend.services.resource_discovery_service import (
    discover_resources,
    get_resource_search_history,
    get_designer_saved_resources,
    record_resource_search,
    remove_designer_resource,
    save_designer_resource,
)


router = APIRouter(prefix="/api/workflow", tags=["submission workflow"])
MAX_PDF_BYTES = 25 * 1024 * 1024


@router.get("/account/me")
def account_profile(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    try:
        return get_account_profile(current_user.user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/account/me/preferences")
def account_preferences(payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    try:
        return update_account_preferences(current_user.user_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _actor(identity: AuthenticatedUser):
    return actor_record(identity.user_id, identity.role, identity.name, identity.email)


def _submission(submission_id: str):
    record = find_submission(submission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Submission not found")
    return record


def _authorized(identity: AuthenticatedUser, record):
    actor = _actor(identity)
    if not authorize_submission_access(actor, record):
        raise HTTPException(status_code=404, detail="Submission not found")
    return actor


@router.get("/curricula")
def institute_curricula(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute")
    try:
        return prepared_curricula_for_institute(_actor(current_user))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Workflow database unavailable") from exc


@router.post("/curricula/{document_id}/handoff")
def designer_handoff(document_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    try:
        if not _actor(current_user).get("institute_id"):
            raise HTTPException(status_code=403, detail="Your Designer account must be linked to an institution first")
        record = handoff_curriculum(designer_id=current_user.user_id, document_id=document_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Workflow database unavailable") from exc
    if not record:
        raise HTTPException(status_code=404, detail="Prepared curriculum not found")
    return {"document_id": record["document_id"], "handoff_status": record["handoff_status"]}


@router.post("/submissions/prepared")
def submit_prepared_curriculum(payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    """Submit the Designer's exact handed-off PDF without a second upload."""
    require_role(current_user, "institute")
    actor = _actor(current_user)
    curriculum_id = str(payload.get("curriculum_id", "")).strip()
    document_id = str(payload.get("document_id", "")).strip()
    if not curriculum_id or not document_id:
        raise HTTPException(status_code=422, detail="curriculum_id and document_id are required")
    try:
        prepared = get_prepared_metadata(actor, curriculum_id, document_id)
        if not prepared or prepared.get("handoff_status") != "Ready for institute":
            raise HTTPException(status_code=404, detail="Handed-off curriculum not found for your institution")
        if not prepared.get("original_file_id"):
            raise HTTPException(status_code=409, detail="The prepared PDF is unavailable")
        reserved = reserve_submission(
            user=actor,
            prepared=prepared,
            curriculum_name=prepared.get("filename", curriculum_id),
        )
        try:
            return finalize_submission(
                reserved["submission_id"],
                document_id=prepared["document_id"],
                filename=prepared["filename"],
                file_id=prepared["original_file_id"],
            )
        except (RuntimeError, PyMongoError):
            fail_submission_upload(reserved["submission_id"])
            raise
    except HTTPException:
        raise
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="A concurrent submission is being prepared; refresh and retry") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Submission storage is unavailable") from exc


@router.post("/submissions")
async def submit_curriculum(
    curriculum_id: str = Form(...),
    document_id: str = Form(...),
    curriculum_name: str = Form(""),
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    require_role(current_user, "institute")
    actor = _actor(current_user)
    try:
        prepared = get_prepared_metadata(actor, curriculum_id.strip(), document_id.strip())
        if not prepared or prepared.get("handoff_status") != "Ready for institute":
            raise HTTPException(status_code=404, detail="Prepared curriculum not found for your institution")
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        data = await file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF must be 25 MB or smaller")
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF")
        if data != read_original_pdf(prepared["original_file_id"])[0]:
            raise HTTPException(status_code=409, detail="Submit the exact PDF version prepared by the Designer")
        reserved = reserve_submission(
            user=actor,
            prepared=prepared,
            curriculum_name=curriculum_name.strip() or prepared.get("filename", curriculum_id),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="A concurrent submission is being prepared; refresh and retry") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        pages = extract_pages_from_pdf(data)
        text = combine_pdf_pages(pages)
        indexed_filename = f"submission-{reserved['submission_id']}.pdf"
        submission_document_id = generate_document_id(data)
        total_chunks, already_indexed = process_and_store_pdf(
            text,
            indexed_filename,
            pages=pages,
            document_id=submission_document_id,
            source_type="submitted_curriculum",
            programme=prepared.get("programme", "B.Tech"),
            branch=prepared.get("branch", "CSE"),
            curriculum_id=curriculum_id.strip(),
            year=prepared.get("year"),
            version=str(reserved["version"]),
            owner_id=prepared["owner_id"],
        )
        if not total_chunks or already_indexed:
            raise RuntimeError("Unable to create a new immutable submission index")
        file_id = store_original_pdf(data, file.filename, {
            "submission_id": reserved["submission_id"],
            "document_id": submission_document_id,
            "designer_id": prepared["owner_id"],
            "institute_id": actor["institute_id"],
            "uploaded_by": actor["user_id"],
            "version": reserved["version"],
        })
        return finalize_submission(
            reserved["submission_id"],
            document_id=submission_document_id,
            filename=file.filename,
            file_id=file_id,
        )
    except (ValueError, RuntimeError) as exc:
        fail_submission_upload(reserved["submission_id"])
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PyMongoError as exc:
        fail_submission_upload(reserved["submission_id"])
        raise HTTPException(status_code=503, detail="Submission storage is unavailable") from exc


@router.get("/submissions")
def reviewer_queue(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "reviewer")
    try:
        return list_pending_submissions()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Workflow database unavailable") from exc


@router.get("/admin/submissions")
def admin_submission_register(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    from backend.data.database import get_workflow_database
    db = get_workflow_database()
    rows = db.curriculum_submissions.find({"status": {"$in": ["Pending", "Accepted", "Revision Required", "Rejected", "Published"]}}).sort("submitted_at", -1)
    result = []
    for row in rows:
        institute = db.institutions.find_one({"institute_id": row["institute_id"]}) or {}
        designer = db.users.find_one({"user_id": row["designer_id"]}, {"name": 1}) or {}
        analysis = db.submission_analyses.find_one({"submission_id": row["submission_id"]}, sort=[("created_at", -1)]) or {}
        result.append({
            **serialize_submission(row), "institute_name": institute.get("name", "Institution"),
            "designer_name": designer.get("name", "Designer"),
            "latest_score": (analysis.get("report") or {}).get("overall_score"),
        })
    return result


@router.get("/publications/eligible")
def publication_eligible(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute")
    institute_id = _actor(current_user).get("institute_id")
    if not institute_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
    return list_publication_eligible(institute_id)


@router.get("/publications")
def published_curricula(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute", "designer")
    actor = _actor(current_user)
    if current_user.role == "institute":
        institute_id = actor.get("institute_id")
        if not institute_id:
            raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
        return list_published_curricula(institute_id)
    institute_id = actor.get("institute_id")
    if not institute_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
    return [row for row in list_published_curricula(institute_id) if row["designer_id"] == current_user.user_id]


@router.post("/submissions/{submission_id}/publish")
def publish_accepted_submission(submission_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute")
    institute_id = _actor(current_user).get("institute_id")
    if not institute_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
    try:
        return publish_submission(submission_id=submission_id, institute_id=institute_id, publisher_id=current_user.user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/submissions/{submission_id}/feedback")
def submit_institute_feedback(submission_id: str, payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute")
    institute_id = _actor(current_user).get("institute_id")
    if not institute_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
    try:
        return record_institute_feedback(
            submission_id=submission_id, institute_id=institute_id, author_id=current_user.user_id,
            kind=str(payload.get("kind", "feedback")), category=str(payload.get("category", "General")),
            observation=str(payload.get("observation", "")), suggested_change=str(payload.get("suggested_change", "")),
            priority=str(payload.get("priority", "Medium")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/submissions/mine")
def my_submissions(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute", "designer")
    actor = _actor(current_user)
    from backend.data.database import get_workflow_database
    from backend.services.workflow_service import serialize_submission
    if actor["role"] == "designer":
        query = {"designer_id": actor["user_id"]}
    else:
        if not actor.get("institute_id"):
            raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
        query = {"institute_id": actor["institute_id"]}
    results = [serialize_submission(row) for row in get_workflow_database().curriculum_submissions.find(query).sort("submitted_at", -1)]
    if actor["role"] == "designer":
        requests = list_change_requests(role="designer", user_id=actor["user_id"])
        for result in results:
            result["change_requests"] = [request for request in requests if request["submission_id"] == result["submission_id"]]
    return results


@router.get("/publications/{submission_id}/curriculum")
def published_curriculum_structure(submission_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "institute")
    actor = _actor(current_user)
    if not actor.get("institute_id"):
        raise HTTPException(status_code=403, detail="Your account is not linked to an institution")
    record = find_submission(submission_id)
    if not record or record.get("status") != "Published" or record.get("institute_id") != actor["institute_id"]:
        raise HTTPException(status_code=404, detail="Published curriculum not found")
    try:
        return extract_structured_curriculum(
            curriculum_id=record["curriculum_id"],
            document_id=record["document_id"],
            owner_id=record["designer_id"],
        )
    except CurriculumNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Published curriculum document is unavailable") from exc
    except AmbiguousCurriculumError as exc:
        raise HTTPException(status_code=409, detail="Published curriculum version is ambiguous") from exc
    except InvalidCurriculumMetadataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/improvements")
def designer_improvements(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    return improvement_history(current_user.user_id)


@router.get("/submissions/history")
def review_history(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "reviewer", "admin")
    from backend.data.database import get_workflow_database
    db = get_workflow_database()
    rows = db.curriculum_submissions.find({"status": {"$in": ["Accepted", "Published", "Revision Required", "Rejected"]}}).sort("submitted_at", -1)
    result = []
    for row in rows:
        institute = db.institutions.find_one({"institute_id": row["institute_id"]}) or {}
        submission = serialize_submission(row)
        for review in submission["review_history"]:
            reviewer = db.users.find_one({"user_id": review.get("reviewer_id")}, {"name": 1}) or {}
            review["reviewer_name"] = reviewer.get("name", "Reviewer")
        result.append({**submission, "institute_name": institute.get("name", "Institution")})
    return result


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    record = _submission(submission_id)
    _authorized(current_user, record)
    from backend.data.database import get_workflow_database
    db = get_workflow_database()
    previous = db.curriculum_submissions.find({
        "designer_id": record["designer_id"], "institute_id": record["institute_id"],
        "curriculum_id": record["curriculum_id"], "version": {"$lt": record["version"]},
        "status": {"$ne": "Uploading"},
    }).sort("version", -1)
    previous_versions = []
    for older in previous:
        older_row = serialize_submission(older)
        older_row["analyses"] = analysis_history(older["submission_id"])
        previous_versions.append(older_row)
    return {
        **serialize_submission(record), "analyses": analysis_history(submission_id),
        "previous_versions": previous_versions,
    }


@router.get("/submissions/{submission_id}/document")
def submission_document(submission_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    record = _submission(submission_id)
    _authorized(current_user, record)
    if not record.get("original_file_id"):
        raise HTTPException(status_code=404, detail="Submitted document is unavailable")
    try:
        content, filename = read_original_pdf(record["original_file_id"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Submitted document is unavailable") from exc
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}", "Cache-Control": "private, no-store"},
    )


@router.post("/submissions/{submission_id}/analyze", response_model=AnalyzerAnalysis)
def analyze_submission(submission_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "reviewer")
    record = _submission(submission_id)
    if record.get("status") != "Pending":
        raise HTTPException(status_code=409, detail="Only pending submissions can be analyzed in the review workflow")
    try:
        curriculum = extract_structured_curriculum(
            curriculum_id=record["curriculum_id"],
            document_id=record["document_id"],
            owner_id=record["designer_id"],
        )
        score: AnalyzerScore = enrich_score_with_aicte_evidence(score_structured_curriculum(curriculum))
    except CurriculumNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AmbiguousCurriculumError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidCurriculumMetadataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if score.aicte_reference_available is False:
        issues_available, issues, issues_error = False, [], score.aicte_reference_message
    else:
        issues_available, issues, issues_error = generate_analyzer_issues(score)
    report = AnalyzerAnalysis(
        **score.model_dump(),
        issues_available=issues_available,
        issues_error=issues_error,
        issues=issues,
        decision_support=build_decision_support(score),
    )
    record_analysis(record, current_user.user_id, report.model_dump(mode="json"))
    if record.get("version", 1) > 1:
        update_requests_linked_to_submission(submission_id, "Under Re-review")
    return report


@router.post("/submissions/{submission_id}/decision")
def reviewer_decision(submission_id: str, payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "reviewer")
    _submission(submission_id)
    decision = str(payload.get("decision", "")).strip().lower()
    feedback = str(payload.get("feedback", ""))
    justification = str(payload.get("justification", ""))
    histories = analysis_history(submission_id)
    recommendation = None
    if histories:
        recommendation = (histories[0].get("report") or {}).get("decision_support", {}).get("decision")
    decision_labels = {"accept": "ACCEPT", "review": "REVISE", "reject": "REJECT"}
    if recommendation and decision_labels.get(decision) != recommendation and not justification.strip():
        raise HTTPException(status_code=422, detail="Provide a short justification when the final decision differs from the analyzer recommendation")
    try:
        result = decide_submission(submission_id=submission_id, reviewer_id=current_user.user_id, decision=decision, feedback=feedback, justification=justification, recommendation=recommendation)
        if decision == "review" and result.get("version", 1) > 1:
            update_requests_linked_to_submission(submission_id, "Reopened")
        elif decision == "reject" and result.get("version", 1) > 1:
            update_requests_linked_to_submission(submission_id, "Closed")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/change-requests")
def workflow_change_requests(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer", "reviewer", "admin")
    return list_change_requests(role=current_user.role, user_id=current_user.user_id)


@router.get("/notifications")
def workflow_notifications(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    return list_user_notifications(current_user.user_id)


@router.patch("/notifications/{notification_id}/read")
def read_workflow_notification(notification_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    if not mark_user_notification_read(current_user.user_id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"notification_id": notification_id, "read": True}


@router.post("/notifications/read-all")
def read_all_workflow_notifications(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    mark_all_user_notifications_read(current_user.user_id)
    return {"updated": True}


@router.patch("/change-requests/{submission_id}/{review_id}/{request_id}")
def update_workflow_change_request(submission_id: str, review_id: str, request_id: str, payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    try:
        return update_change_request(
            user_id=current_user.user_id,
            submission_id=submission_id,
            review_id=review_id,
            request_id=request_id,
            status=str(payload.get("status", "In Progress")),
            response=str(payload.get("response", "")),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Change request not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/resources/search")
def search_resources(subject: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    try:
        result = discover_resources(subject)
        record_resource_search(current_user.user_id, result["subject"])
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Saved resource storage is unavailable") from exc


@router.get("/resources/saved")
def saved_resources(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    return get_designer_saved_resources(current_user.user_id)


@router.get("/resources/history")
def resource_search_history(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    return get_resource_search_history(current_user.user_id)


@router.post("/resources/saved")
def save_resource(payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    try:
        return save_designer_resource(current_user.user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Saved resource storage is unavailable") from exc


@router.delete("/resources/saved/{resource_id}")
def unsave_resource(resource_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "designer")
    if not remove_designer_resource(current_user.user_id, resource_id):
        raise HTTPException(status_code=404, detail="Saved resource not found")
    return {"removed": True}


@router.get("/institutions")
def admin_institutions(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    return list_institutions()


@router.get("/admin/audit-events")
def admin_audit_events(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    try:
        return list_audit_events()
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Workflow activity is unavailable") from exc


@router.post("/institutions")
def add_institution(payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="Institution name is required")
    try:
        return create_institution(name)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="An institution with this name already exists") from exc


@router.get("/users")
def admin_users(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    return list_users()


@router.post("/users")
def add_user(payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    try:
        return create_institute_user(
            name=str(payload.get("name", "")),
            email=str(payload.get("email", "")),
            role=str(payload.get("role", "")),
            password=str(payload.get("password", "")),
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="A user with this email or ID already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/users/{user_id}/institution")
def set_user_institution(user_id: str, payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    try:
        return assign_institution(user_id, payload.get("institute_id"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/users/{user_id}")
def edit_user(user_id: str, payload: dict, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin")
    try:
        return update_user_access(user_id, role=payload.get("role"), status=payload.get("status"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

