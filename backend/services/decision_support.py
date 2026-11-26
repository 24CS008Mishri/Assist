"""Transparent, advisory reviewer recommendations from existing analyzer rules."""

from typing import Any, Dict, List

from backend.models.analyzer_issue_schemas import DecisionSupport
from backend.models.analyzer_scoring_schemas import AnalyzerScore, CheckStatus


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def build_decision_support(score: AnalyzerScore) -> DecisionSupport:
    reasons: List[Dict[str, Any]] = []
    checks_seen = 0
    evaluable_seen = 0
    explicit_critical = False
    mandatory_evidence_missing = False

    for criterion in score.criteria:
        for check in criterion.checks:
            checks_seen += 1
            status = _value(check.status)
            rule_type = _value(check.rule_type)
            if status != CheckStatus.NOT_EVALUABLE.value:
                evaluable_seen += 1
            elif rule_type == "AICTE_MANDATORY":
                mandatory_evidence_missing = True
            if status not in {CheckStatus.FAIL.value, CheckStatus.PARTIAL.value}:
                continue

            mandatory_failure = (
                rule_type == "AICTE_MANDATORY"
                and status == CheckStatus.FAIL.value
                and bool(check.aicte_evidence)
                and bool(check.curriculum_evidence)
            )
            explicit_critical = explicit_critical or mandatory_failure
            reasons.append({
                "finding_id": check.check_id,
                "criterion": criterion.criterion,
                "title": check.title,
                "severity": "CRITICAL" if mandatory_failure else "HIGH" if status == CheckStatus.FAIL.value else "MEDIUM",
                "status": status,
                "rule_type": rule_type,
                "explanation": check.deduction_reason or f"The {check.title} check is {status}.",
                "recommended_action": (
                    f"Correct {check.title.lower()} and provide evidence that addresses this check."
                ),
                "expected": check.expected,
                "actual": check.actual,
                "aicte_evidence": check.aicte_evidence,
                "curriculum_evidence": check.curriculum_evidence,
            })

    insufficient = (
        score.aicte_reference_available is False
        or score.overall_score is None
        or score.low_coverage
        or checks_seen == 0
        or evaluable_seen == 0
        or mandatory_evidence_missing
    )
    if insufficient:
        decision = "INSUFFICIENT_EVIDENCE"
        summary = (
            score.aicte_reference_message
            if score.aicte_reference_available is False and score.aicte_reference_message
            else "The available document evidence is not sufficient for a reliable recommendation. A Reviewer must verify missing evidence manually."
        )
    elif explicit_critical:
        decision = "REJECT"
        summary = "An evidenced failure of an explicitly configured mandatory criterion requires a documented Reviewer decision."
    elif reasons:
        decision = "REVISE"
        summary = f"{len(reasons)} evaluated check(s) are failed or partial and have actionable evidence to address."
    else:
        decision = "ACCEPT"
        summary = "No failed or partial evaluated checks were found. The Reviewer must still confirm the submitted evidence and applicable requirements."

    return DecisionSupport(decision=decision, summary=summary, reasons=reasons)
