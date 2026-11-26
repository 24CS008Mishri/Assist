from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import AuthenticatedUser, require_authenticated_user, require_role
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


router = APIRouter(prefix="/api/analyzer", tags=["analyzer"])


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


@router.post(
    "/extract/{curriculum_id}",
    response_model=StructuredCurriculum,
)
def extract_curriculum_endpoint(
    curriculum_id: str,
    document_id: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> StructuredCurriculum:
    require_role(current_user, "designer")
    try:
        return extract_structured_curriculum(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=current_user.user_id,
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
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AnalyzerScore:
    require_role(current_user, "designer")
    try:
        return _build_analyzer_score(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=current_user.user_id,
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
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AnalyzerAnalysis:
    require_role(current_user, "designer")
    try:
        score = _build_analyzer_score(
            curriculum_id=curriculum_id,
            document_id=document_id,
            owner_id=current_user.user_id,
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
    )
