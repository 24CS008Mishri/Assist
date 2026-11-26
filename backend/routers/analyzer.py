from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import AuthenticatedUser, require_authenticated_user, require_role
from backend.core.analyzer_criteria import CHECK_DEFINITIONS, CRITERION_LABELS
from backend.models.analyzer_schemas import StructuredCurriculum
from backend.models.analyzer_issue_schemas import AnalyzerAnalysis
from backend.models.analyzer_scoring_schemas import AnalyzerScore
from backend.services.aicte_evidence_service import enrich_score_with_aicte_evidence
from backend.services.analyzer_llm_service import generate_analyzer_issues
from backend.services.curriculum_extraction_service import (
    AmbiguousCurriculumError,
    CurriculumNotFoundError,
    InvalidCurriculumMetadataError,
    extract_structured_curriculum,
)
from backend.services.scoring_service import score_structured_curriculum
from backend.services.workflow_service import find_submission
from backend.services.decision_support import build_decision_support


router = APIRouter(prefix="/api/analyzer", tags=["analyzer"])


@router.get("/criteria")
def analyzer_criteria(current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_role(current_user, "admin", "reviewer")
    return [{
        "check_id": item.check_id,
        "criterion": item.criterion,
        "criterion_label": CRITERION_LABELS.get(item.criterion, item.criterion),
        "title": item.title,
        "maximum_marks": item.maximum_marks,
        "basis": item.rule_type,
        "expected": item.expected,
        "explanation": item.baseline_note,
        "availability_policy": item.availability_policy,
    } for item in CHECK_DEFINITIONS]


def _build_analyzer_score(
    curriculum_id: str,
    document_id: Optional[str],
    owner_id: str,
) -> AnalyzerScore:
    curriculum = extract_structured_curriculum(
        curriculum_id=curriculum_id,
        document_id=document_id,
        owner_id=owner_id,
    )
    score = score_structured_curriculum(curriculum)
    return enrich_score_with_aicte_evidence(score)


def _submission_analysis_scope(current_user: AuthenticatedUser, curriculum_id: str, document_id: Optional[str], submission_id: Optional[str]):
    require_role(current_user, "reviewer")
    if not submission_id:
        raise HTTPException(status_code=400, detail="submission_id is required; analyze only an official submission")
    submission = find_submission(submission_id)
    if not submission or submission.get("status") != "Pending":
        raise HTTPException(status_code=404, detail="Pending submission not found")
    if submission.get("curriculum_id") != curriculum_id or (document_id and submission.get("document_id") != document_id):
        raise HTTPException(status_code=404, detail="Submission document does not match the requested curriculum")
    return submission


@router.post(
    "/extract/{curriculum_id}",
    response_model=StructuredCurriculum,
)
def extract_curriculum_endpoint(
    curriculum_id: str,
    document_id: Optional[str] = Query(None),
    submission_id: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> StructuredCurriculum:
    submission = _submission_analysis_scope(current_user, curriculum_id, document_id, submission_id)
    try:
        return extract_structured_curriculum(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=submission["designer_id"],
        )
    except CurriculumNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AmbiguousCurriculumError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidCurriculumMetadataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/score/{curriculum_id}",
    response_model=AnalyzerScore,
)
def score_curriculum_endpoint(
    curriculum_id: str,
    document_id: Optional[str] = Query(None),
    submission_id: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AnalyzerScore:
    submission = _submission_analysis_scope(current_user, curriculum_id, document_id, submission_id)
    try:
        return _build_analyzer_score(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=submission["designer_id"],
        )
    except CurriculumNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AmbiguousCurriculumError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidCurriculumMetadataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/analyze/{curriculum_id}",
    response_model=AnalyzerAnalysis,
)
def analyze_curriculum_endpoint(
    curriculum_id: str,
    document_id: Optional[str] = Query(None),
    submission_id: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AnalyzerAnalysis:
    submission = _submission_analysis_scope(current_user, curriculum_id, document_id, submission_id)
    try:
        score = _build_analyzer_score(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=submission["designer_id"],
        )
    except CurriculumNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AmbiguousCurriculumError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidCurriculumMetadataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if score.aicte_reference_available is False:
        issues_available, issues, issues_error = (
            False,
            [],
            score.aicte_reference_message,
        )
    else:
        issues_available, issues, issues_error = generate_analyzer_issues(score)
    return AnalyzerAnalysis(
        **score.model_dump(),
        issues_available=issues_available,
        issues_error=issues_error,
        issues=issues,
        decision_support=build_decision_support(score),
    )
