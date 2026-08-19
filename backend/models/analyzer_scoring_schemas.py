from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from backend.models.analyzer_schemas import EvidenceReference


class CheckStatus(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class DocumentScope(str, Enum):
    FULL_CURRICULUM = "FULL_CURRICULUM"
    PARTIAL_CURRICULUM = "PARTIAL_CURRICULUM"


class RuleType(str, Enum):
    AICTE_MANDATORY = "AICTE_MANDATORY"
    AICTE_MODEL_REFERENCE = "AICTE_MODEL_REFERENCE"
    ANALYZER_DERIVED = "ANALYZER_DERIVED"


class AicteEvidenceReference(BaseModel):
    source: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    heading: Optional[str] = None
    excerpt: str


class ScoringCheck(BaseModel):
    check_id: str
    criterion: str
    title: str
    rule_type: RuleType
    status: CheckStatus
    obtained_marks: Optional[float] = None
    maximum_marks: float
    expected: Any
    actual: Any = None
    deduction_reason: str
    aicte_evidence: List[AicteEvidenceReference] = Field(default_factory=list)
    curriculum_evidence: List[EvidenceReference] = Field(default_factory=list)


class CriterionScore(BaseModel):
    criterion: str
    label: str
    score: Optional[float] = None
    weight: float
    obtained_marks: float
    evaluable_maximum_marks: float
    configured_maximum_marks: float = 100
    evaluation_coverage: float
    low_coverage: bool
    checks: List[ScoringCheck] = Field(default_factory=list)


class AnalyzerScore(BaseModel):
    curriculum_id: str
    document_id: str
    scoring_version: str
    document_scope: DocumentScope
    scope_reason: str
    overall_score: Optional[float] = None
    evaluable_weight: float
    overall_evaluation_coverage: float
    low_coverage: bool
    aicte_reference_available: Optional[bool] = None
    aicte_reference_message: Optional[str] = None
    criteria: List[CriterionScore] = Field(default_factory=list)
