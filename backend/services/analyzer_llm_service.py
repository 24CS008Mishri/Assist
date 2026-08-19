import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from langchain_groq import ChatGroq
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from backend.core.config import get_settings
from backend.models.analyzer_issue_schemas import (
    AnalyzerIssue,
    IssueSeverity,
)
from backend.models.analyzer_schemas import EvidenceReference
from backend.models.analyzer_scoring_schemas import (
    AicteEvidenceReference,
    AnalyzerScore,
    CheckStatus,
    RuleType,
    ScoringCheck,
)


MAX_ANALYZER_ISSUES = 7
ISSUES_UNAVAILABLE_MESSAGE = "AI recommendations temporarily unavailable"

# Related deterministic checks are represented by one LLM issue to avoid
# repeating the same underlying curriculum gap in the UI.
_DEDUPLICATION_GROUPS: Dict[str, str] = {
    "structure.project_internship": "work_integrated_learning",
    "compliance.internship": "work_integrated_learning",
    "compliance.project": "work_integrated_learning",
    "industry.projects": "work_integrated_learning",
    "industry.internship": "work_integrated_learning",
    "assessment.project_evaluation": "work_integrated_learning",
    "assessment.internship_evaluation": "work_integrated_learning",
    "structure.professional_elective": "elective_coverage",
    "structure.open_elective": "elective_coverage",
    "industry.emerging_electives": "elective_coverage",
    "industry.machine_learning": "machine_learning_coverage",
    "skills.machine_learning_data": "machine_learning_coverage",
    "industry.cyber_security": "cyber_security_coverage",
    "skills.cyber_security": "cyber_security_coverage",
    "industry.practical_programming": "practical_exposure",
    "resources.labs_practicals": "practical_exposure",
    "resources.experimental": "practical_exposure",
    "skills.projects_practical": "practical_exposure",
    "outcomes.course_coverage": "learning_outcome_documentation",
    "outcomes.objective_coverage": "learning_outcome_documentation",
    "outcomes.density": "learning_outcome_documentation",
    "outcomes.action_verbs": "learning_outcome_documentation",
    "outcomes.core_course_coverage": "learning_outcome_documentation",
    "assessment.course_coverage": "assessment_documentation",
    "assessment.theory_practical": "assessment_documentation",
    "assessment.practical_alignment": "assessment_documentation",
    "resources.reference_coverage": "learning_resources",
    "resources.online_learning": "learning_resources",
    "resources.project_lab": "learning_resources",
    "compliance.essential_core": "core_skill_coverage",
    "skills.programming": "core_skill_coverage",
    "skills.data_structures_algorithms": "core_skill_coverage",
    "skills.mathematical_foundations": "core_skill_coverage",
    "skills.computer_architecture": "core_skill_coverage",
    "skills.operating_systems": "core_skill_coverage",
    "skills.databases": "core_skill_coverage",
    "skills.computer_networks": "core_skill_coverage",
    "skills.theory_computation": "core_skill_coverage",
    "skills.compiler_processing": "core_skill_coverage",
}


@dataclass(frozen=True)
class SelectedFinding:
    finding_id: str
    criterion: str
    group_key: str
    checks: Tuple[ScoringCheck, ...]

    @property
    def related_check_ids(self) -> List[str]:
        return [check.check_id for check in self.checks]


class _GeneratedIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(min_length=1)
    problem: str = Field(min_length=1, max_length=600)
    why_it_matters: str = Field(min_length=1, max_length=800)
    recommended_solution: str = Field(min_length=1, max_length=1000)
    severity: IssueSeverity

    @field_validator("finding_id", "problem", "why_it_matters", "recommended_solution")
    @classmethod
    def _strip_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Issue text must not be blank")
        return cleaned


class _GeneratedIssueBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: List[_GeneratedIssue]


@lru_cache(maxsize=1)
def get_analyzer_llm() -> ChatGroq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY must be set before generating analyzer issues")
    return ChatGroq(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0,
        timeout=20,
        max_retries=1,
    )


def _priority(check: ScoringCheck) -> Tuple[int, float, float, str]:
    key = (check.rule_type, check.status)
    order = {
        (RuleType.AICTE_MANDATORY, CheckStatus.FAIL): 0,
        (RuleType.AICTE_MANDATORY, CheckStatus.PARTIAL): 1,
        (RuleType.AICTE_MODEL_REFERENCE, CheckStatus.FAIL): 2,
        (RuleType.ANALYZER_DERIVED, CheckStatus.FAIL): 3,
        (RuleType.AICTE_MODEL_REFERENCE, CheckStatus.PARTIAL): 4,
        (RuleType.ANALYZER_DERIVED, CheckStatus.PARTIAL): 5,
    }
    obtained = check.obtained_marks or 0.0
    loss_ratio = (
        (check.maximum_marks - obtained) / check.maximum_marks
        if check.maximum_marks
        else 0.0
    )
    return (
        order.get(key, 99),
        -loss_ratio,
        -check.maximum_marks,
        check.check_id,
    )


def select_issue_findings(
    score: AnalyzerScore,
    limit: int = MAX_ANALYZER_ISSUES,
) -> List[SelectedFinding]:
    candidates = sorted(
        (
            check
            for criterion in score.criteria
            for check in criterion.checks
            if check.status in {CheckStatus.FAIL, CheckStatus.PARTIAL}
        ),
        key=_priority,
    )
    grouped: Dict[str, List[ScoringCheck]] = {}
    group_order: List[str] = []
    for check in candidates:
        group_key = _DEDUPLICATION_GROUPS.get(check.check_id, check.check_id)
        if group_key not in grouped:
            grouped[group_key] = []
            group_order.append(group_key)
        grouped[group_key].append(check)

    selected: List[SelectedFinding] = []
    for index, group_key in enumerate(group_order[: max(0, limit)], start=1):
        checks = tuple(grouped[group_key])
        selected.append(
            SelectedFinding(
                finding_id=f"finding_{index:03d}",
                criterion=checks[0].criterion,
                group_key=group_key,
                checks=checks,
            )
        )
    return selected


def _unique_evidence(items: Iterable[Any], limit: int = 12) -> List[Any]:
    result = []
    seen = set()
    for item in items:
        source = getattr(item, "source", None)
        key = (
            source,
            item.page_number,
            item.chunk_index,
            item.excerpt,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _prompt_evidence(items: Sequence[Any]) -> List[Dict[str, Any]]:
    evidence = []
    for item in items[:2]:
        value = item.model_dump(mode="json")
        value["excerpt"] = value.get("excerpt", "")[:450]
        evidence.append(value)
    return evidence


def _finding_payload(finding: SelectedFinding) -> Dict[str, Any]:
    return {
        "finding_id": finding.finding_id,
        "criterion": finding.criterion,
        "related_checks": [
            {
                "check_id": check.check_id,
                "check": check.title,
                "status": check.status.value,
                "rule_type": check.rule_type.value,
                "expected": check.expected,
                "actual": check.actual,
                "deduction_reason": check.deduction_reason,
                "aicte_evidence": _prompt_evidence(check.aicte_evidence),
                "curriculum_evidence": _prompt_evidence(check.curriculum_evidence),
            }
            for check in finding.checks
        ],
    }


def build_issue_prompt(findings: Sequence[SelectedFinding]) -> str:
    payload = [_finding_payload(finding) for finding in findings]
    return (
        "You generate concise advisory explanations for a B.Tech CSE curriculum "
        "analyzer. Use only the supplied findings and evidence. Do not calculate, "
        "change, infer, or mention any score or percentage. Do not invent AICTE "
        "rules or missing curriculum facts. AICTE_MODEL_REFERENCE means a model "
        "comparison, never a regulatory violation. AICTE_MANDATORY may be called "
        "mandatory only when that exact rule type is supplied. Do not claim approval "
        "or rejection authority. Recommend exact curriculum changes only when the "
        "evidence supports them; otherwise recommend verification or a conservative "
        "review. If evidence is thin, explicitly qualify the explanation.\n\n"
        "Return one issue for every finding_id, in the same order, as one strict JSON "
        "object and no markdown or prose outside it. Use exactly this shape:\n"
        '{"issues":[{"finding_id":"finding_001","problem":"...",'
        '"why_it_matters":"...","recommended_solution":"...",'
        '"severity":"CRITICAL|HIGH|MEDIUM|LOW"}]}\n\n'
        f"Selected findings:\n{json.dumps(payload, ensure_ascii=False, default=str)}"
    )


def parse_issue_response(
    content: Any,
    findings: Sequence[SelectedFinding],
) -> List[_GeneratedIssue]:
    if not isinstance(content, str):
        raise ValueError("Analyzer issue response must be a JSON string")
    try:
        raw = json.loads(content)
        parsed = _GeneratedIssueBatch.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Analyzer issue response failed strict JSON validation") from exc

    expected_ids = [finding.finding_id for finding in findings]
    actual_ids = [issue.finding_id for issue in parsed.issues]
    if actual_ids != expected_ids:
        raise ValueError("Analyzer issue response finding IDs or ordering are invalid")
    return parsed.issues


def _to_analyzer_issue(
    generated: _GeneratedIssue,
    finding: SelectedFinding,
    issue_index: int,
) -> AnalyzerIssue:
    aicte_evidence: List[AicteEvidenceReference] = _unique_evidence(
        evidence
        for check in finding.checks
        for evidence in check.aicte_evidence
    )
    curriculum_evidence: List[EvidenceReference] = _unique_evidence(
        evidence
        for check in finding.checks
        for evidence in check.curriculum_evidence
    )
    return AnalyzerIssue(
        issue_id=f"issue_{issue_index:03d}",
        criterion=finding.criterion,
        related_check_ids=finding.related_check_ids,
        severity=generated.severity,
        problem=generated.problem,
        why_it_matters=generated.why_it_matters,
        recommended_solution=generated.recommended_solution,
        aicte_evidence=aicte_evidence,
        curriculum_evidence=curriculum_evidence,
    )


def generate_analyzer_issues(
    score: AnalyzerScore,
    llm: Optional[Any] = None,
) -> Tuple[bool, List[AnalyzerIssue], Optional[str]]:
    findings = select_issue_findings(score)
    if not findings:
        return True, [], None
    try:
        client = llm if llm is not None else get_analyzer_llm()
        response = client.invoke(build_issue_prompt(findings))
        content = getattr(response, "content", response)
        generated = parse_issue_response(content, findings)
        issues = [
            _to_analyzer_issue(item, finding, index)
            for index, (item, finding) in enumerate(
                zip(generated, findings),
                start=1,
            )
        ]
        return True, issues, None
    except Exception:
        return False, [], ISSUES_UNAVAILABLE_MESSAGE
