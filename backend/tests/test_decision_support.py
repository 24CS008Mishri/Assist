import unittest

from backend.models.analyzer_schemas import EvidenceReference
from backend.models.analyzer_scoring_schemas import (
    AnalyzerScore,
    AvailabilityPolicy,
    CheckStatus,
    CriterionScore,
    DocumentScope,
    RuleType,
    ScoringCheck,
)
from backend.services.decision_support import build_decision_support


def make_score(statuses, *, low_coverage=False, reference_available=True):
    checks = []
    for index, (status, rule_type) in enumerate(statuses):
        checks.append(ScoringCheck(
            check_id=f"check-{index}", criterion="test-criterion", title=f"Check {index}",
            rule_type=rule_type, availability_policy=AvailabilityPolicy.REQUIRED,
            status=status, maximum_marks=10, expected="expected", actual="observed",
            deduction_reason="Evidence gap", aicte_evidence=(
                [{"source": "Official reference", "excerpt": "Requirement evidence"}]
                if rule_type == RuleType.AICTE_MANDATORY and status == CheckStatus.FAIL else []
            ), curriculum_evidence=[EvidenceReference(page_number=2, excerpt="Observed evidence")]
            if status == CheckStatus.FAIL else [],
        ))
    criterion = CriterionScore(
        criterion="test-criterion", label="Test criterion", score=80, weight=1,
        obtained_marks=80, evaluable_maximum_marks=100, evaluation_coverage=80,
        low_coverage=low_coverage, checks=checks,
    )
    return AnalyzerScore(
        curriculum_id="curriculum-1", document_id="document-1", scoring_version="test",
        document_scope=DocumentScope.FULL_CURRICULUM, scope_reason="Complete document",
        overall_score=80, evaluable_weight=100, overall_evaluation_coverage=80,
        low_coverage=low_coverage, aicte_reference_available=reference_available,
        criteria=[criterion],
    )


class DecisionSupportTests(unittest.TestCase):
    def test_partial_check_recommends_revision_with_finding_evidence(self):
        score = make_score([(CheckStatus.PARTIAL, RuleType.ANALYZER_DERIVED)])
        recommendation = build_decision_support(score)
        self.assertEqual(recommendation.decision, "REVISE")
        self.assertEqual(recommendation.reasons[0].finding_id, "check-0")

    def test_only_evidenced_configured_mandatory_failure_can_recommend_reject(self):
        score = make_score([(CheckStatus.FAIL, RuleType.AICTE_MANDATORY)])
        self.assertEqual(build_decision_support(score).decision, "REJECT")

    def test_unevaluable_mandatory_check_requires_manual_review(self):
        score = make_score([
            (CheckStatus.PASS, RuleType.ANALYZER_DERIVED),
            (CheckStatus.NOT_EVALUABLE, RuleType.AICTE_MANDATORY),
        ])
        self.assertEqual(build_decision_support(score).decision, "INSUFFICIENT_EVIDENCE")

    def test_low_coverage_or_missing_reference_never_recommends_accept(self):
        low = make_score([(CheckStatus.PASS, RuleType.ANALYZER_DERIVED)], low_coverage=True)
        unavailable = make_score([(CheckStatus.PASS, RuleType.ANALYZER_DERIVED)], reference_available=False)
        self.assertEqual(build_decision_support(low).decision, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(build_decision_support(unavailable).decision, "INSUFFICIENT_EVIDENCE")

    def test_clean_evaluable_checks_recommend_advisory_accept(self):
        score = make_score([(CheckStatus.PASS, RuleType.ANALYZER_DERIVED)])
        self.assertEqual(build_decision_support(score).decision, "ACCEPT")


if __name__ == "__main__":
    unittest.main()
