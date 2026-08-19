from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.models.analyzer_schemas import EvidenceReference
from backend.models.analyzer_scoring_schemas import (
    AicteEvidenceReference,
    AnalyzerScore,
)


class IssueSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalyzerIssue(BaseModel):
    issue_id: str
    criterion: str
    related_check_ids: List[str]
    severity: IssueSeverity
    problem: str
    why_it_matters: str
    recommended_solution: str
    aicte_evidence: List[AicteEvidenceReference] = Field(default_factory=list)
    curriculum_evidence: List[EvidenceReference] = Field(default_factory=list)


class AnalyzerAnalysis(AnalyzerScore):
    issues_available: bool
    issues_error: Optional[str] = None
    issues: List[AnalyzerIssue] = Field(default_factory=list)
