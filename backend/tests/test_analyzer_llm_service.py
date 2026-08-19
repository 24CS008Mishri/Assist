import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.core.auth import AuthenticatedUser
from backend.models.analyzer_issue_schemas import AnalyzerIssue, IssueSeverity
from backend.models.analyzer_schemas import EvidenceReference, Semester, StructuredCurriculum
from backend.models.analyzer_scoring_schemas import CheckStatus, DocumentScope, RuleType
from backend.routers.analyzer import (
    analyze_curriculum_endpoint,
    score_curriculum_endpoint,
)
from backend.services.analyzer_llm_service import (
    ISSUES_UNAVAILABLE_MESSAGE,
    build_issue_prompt,
    generate_analyzer_issues,
    parse_issue_response,
    select_issue_findings,
)
from backend.services.scoring_service import score_structured_curriculum


_DESIGNER = AuthenticatedUser(user_id="designer-a", role="designer")


def _score():
    curriculum = StructuredCurriculum(
        curriculum_id="xyz-cse-2026",
        document_id="doc-1",
        programme="B.Tech",
        branch="CSE",
    )
    return score_structured_curriculum(curriculum)


def _check(score, check_id):
    return next(
        check
        for criterion in score.criteria
        for check in criterion.checks
        if check.check_id == check_id
    )


def _configure(
    score,
    check_id,
    status,
    rule_type=RuleType.ANALYZER_DERIVED,
):
    check = _check(score, check_id)
    check.status = status
    check.rule_type = rule_type
    if status == CheckStatus.FAIL:
        check.obtained_marks = 0
    elif status == CheckStatus.PARTIAL:
        check.obtained_marks = check.maximum_marks / 2
    elif status == CheckStatus.PASS:
        check.obtained_marks = check.maximum_marks
    else:
        check.obtained_marks = None
    return check


def _valid_response(findings, severity="MEDIUM"):
    return json.dumps(
        {
            "issues": [
                {
                    "finding_id": finding.finding_id,
                    "problem": f"Problem for {finding.group_key}",
                    "why_it_matters": "This may reduce documented curriculum coverage.",
                    "recommended_solution": "Review the supplied evidence and address the documented gap.",
                    "severity": severity,
                }
                for finding in findings
            ]
        }
    )


class FakeLlm:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


class AnalyzerLlmServiceTests(unittest.TestCase):
    def test_only_fail_and_partial_checks_are_selected(self):
        score = _score()
        _configure(score, "structure.total_credits", CheckStatus.FAIL)
        _configure(score, "industry.cloud_distributed", CheckStatus.PARTIAL)
        _configure(score, "skills.databases", CheckStatus.PASS)
        _configure(score, "assessment.course_coverage", CheckStatus.NOT_EVALUABLE)
        selected_ids = {
            check_id
            for finding in select_issue_findings(score)
            for check_id in finding.related_check_ids
        }
        self.assertIn("structure.total_credits", selected_ids)
        self.assertIn("industry.cloud_distributed", selected_ids)
        self.assertNotIn("skills.databases", selected_ids)
        self.assertNotIn("assessment.course_coverage", selected_ids)

    def test_priority_order_is_deterministic(self):
        score = _score()
        _configure(
            score,
            "compliance.environment",
            CheckStatus.PARTIAL,
            RuleType.AICTE_MANDATORY,
        )
        _configure(
            score,
            "structure.total_credits",
            CheckStatus.FAIL,
            RuleType.AICTE_MODEL_REFERENCE,
        )
        _configure(
            score,
            "industry.cloud_distributed",
            CheckStatus.FAIL,
            RuleType.ANALYZER_DERIVED,
        )
        _configure(
            score,
            "structure.semesters",
            CheckStatus.PARTIAL,
            RuleType.AICTE_MODEL_REFERENCE,
        )
        selected = select_issue_findings(score)
        self.assertEqual(
            [finding.related_check_ids[0] for finding in selected[:4]],
            [
                "compliance.environment",
                "structure.total_credits",
                "industry.cloud_distributed",
                "structure.semesters",
            ],
        )

    def test_related_internship_checks_are_deduplicated(self):
        score = _score()
        for check_id in (
            "structure.project_internship",
            "compliance.internship",
            "industry.internship",
        ):
            _configure(score, check_id, CheckStatus.FAIL)
        findings = select_issue_findings(score)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            set(findings[0].related_check_ids),
            {
                "structure.project_internship",
                "compliance.internship",
                "industry.internship",
            },
        )

    def test_selection_is_limited_to_seven_issue_groups(self):
        score = _score()
        check_ids = [
            "structure.total_credits",
            "structure.semesters",
            "structure.category_distribution",
            "structure.professional_core",
            "compliance.induction",
            "compliance.environment",
            "compliance.constitution_ikt",
            "compliance.human_values",
            "industry.cloud_distributed",
        ]
        for check_id in check_ids:
            _configure(score, check_id, CheckStatus.FAIL)
        self.assertEqual(len(select_issue_findings(score)), 7)

    def test_prompt_contains_grounding_rules_and_only_selected_data(self):
        score = _score()
        _configure(score, "structure.total_credits", CheckStatus.FAIL)
        findings = select_issue_findings(score)
        prompt = build_issue_prompt(findings)
        self.assertIn("AICTE_MODEL_REFERENCE", prompt)
        self.assertIn("never a regulatory violation", prompt)
        self.assertIn("structure.total_credits", prompt)
        self.assertNotIn("entire curriculum", prompt.casefold())

    def test_strict_json_and_allowed_severity_validation(self):
        score = _score()
        _configure(score, "structure.total_credits", CheckStatus.FAIL)
        findings = select_issue_findings(score)
        parsed = parse_issue_response(_valid_response(findings, "HIGH"), findings)
        self.assertEqual(parsed[0].severity, IssueSeverity.HIGH)
        with self.assertRaises(ValueError):
            parse_issue_response(_valid_response(findings, "URGENT"), findings)
        with self.assertRaises(ValueError):
            parse_issue_response("```json\n{}\n```", findings)
        blank = json.loads(_valid_response(findings))
        blank["issues"][0]["problem"] = "   "
        with self.assertRaises(ValueError):
            parse_issue_response(json.dumps(blank), findings)

    def test_malformed_response_and_timeout_return_safe_fallback(self):
        score = _score()
        _configure(score, "structure.total_credits", CheckStatus.FAIL)
        available, issues, error = generate_analyzer_issues(
            score,
            llm=FakeLlm(content="not json"),
        )
        self.assertFalse(available)
        self.assertEqual(issues, [])
        self.assertEqual(error, ISSUES_UNAVAILABLE_MESSAGE)

        available, issues, error = generate_analyzer_issues(
            score,
            llm=FakeLlm(error=TimeoutError("timed out")),
        )
        self.assertFalse(available)
        self.assertEqual(issues, [])
        self.assertEqual(error, ISSUES_UNAVAILABLE_MESSAGE)

    def test_successful_batch_preserves_evidence_and_does_not_change_score(self):
        score = _score()
        check = _configure(score, "structure.total_credits", CheckStatus.FAIL)
        check.curriculum_evidence = [
            EvidenceReference(
                page_number=4,
                chunk_index=12,
                excerpt="Submitted total credits: 140",
                fields=["total_credits"],
            )
        ]
        before = score.model_dump()
        findings = select_issue_findings(score)
        llm = FakeLlm(content=_valid_response(findings))
        available, issues, error = generate_analyzer_issues(score, llm=llm)
        self.assertTrue(available)
        self.assertIsNone(error)
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(issues[0].curriculum_evidence[0].page_number, 4)
        self.assertEqual(score.model_dump(), before)

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_analyze_endpoint_returns_mocked_issues(self, build_mock, issues_mock):
        score = _score()
        build_mock.return_value = score
        issues_mock.return_value = (
            True,
            [
                AnalyzerIssue(
                    issue_id="issue_001",
                    criterion="structure",
                    related_check_ids=["structure.total_credits"],
                    severity=IssueSeverity.MEDIUM,
                    problem="Credit coverage differs from the model reference.",
                    why_it_matters="The documented structure differs from the comparison baseline.",
                    recommended_solution="Review the credit structure against the supplied evidence.",
                )
            ],
            None,
        )
        response = analyze_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )
        self.assertTrue(response.issues_available)
        self.assertEqual(response.issues[0].issue_id, "issue_001")
        self.assertEqual(response.overall_score, score.overall_score)

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_analyze_endpoint_keeps_scores_when_llm_is_unavailable(
        self,
        build_mock,
        issues_mock,
    ):
        score = _score()
        build_mock.return_value = score
        issues_mock.return_value = (False, [], ISSUES_UNAVAILABLE_MESSAGE)
        response = analyze_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )
        self.assertFalse(response.issues_available)
        self.assertEqual(response.issues_error, ISSUES_UNAVAILABLE_MESSAGE)
        self.assertEqual(response.overall_score, score.overall_score)
        self.assertEqual(response.criteria, score.criteria)
        self.assertEqual(response.document_scope, score.document_scope)

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_analyze_skips_llm_when_uploaded_aicte_reference_is_unavailable(
        self,
        build_mock,
        issues_mock,
    ):
        score = _score()
        score.aicte_reference_available = False
        score.aicte_reference_message = (
            "Official AICTE reference documents are not currently available."
        )
        score.overall_score = None
        build_mock.return_value = score

        response = analyze_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )

        issues_mock.assert_not_called()
        self.assertFalse(response.issues_available)
        self.assertEqual(response.issues, [])
        self.assertIsNone(response.overall_score)
        self.assertIn("not currently available", response.issues_error)

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_score_and_analyze_responses_preserve_deterministic_values(
        self,
        build_mock,
        issues_mock,
    ):
        score = _score()
        build_mock.return_value = score
        issues_mock.return_value = (False, [], ISSUES_UNAVAILABLE_MESSAGE)

        score_response = score_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )
        analyze_response = analyze_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )

        self.assertEqual(
            analyze_response.document_scope,
            DocumentScope.PARTIAL_CURRICULUM,
        )
        self.assertEqual(
            analyze_response.overall_score,
            score_response.overall_score,
        )
        self.assertEqual(
            [criterion.score for criterion in analyze_response.criteria],
            [criterion.score for criterion in score_response.criteria],
        )
        self.assertEqual(
            [
                (check.check_id, check.status, check.obtained_marks)
                for criterion in analyze_response.criteria
                for check in criterion.checks
            ],
            [
                (check.check_id, check.status, check.obtained_marks)
                for criterion in score_response.criteria
                for check in criterion.checks
            ],
        )

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_analyze_response_retains_full_curriculum_scope(
        self,
        build_mock,
        issues_mock,
    ):
        curriculum = StructuredCurriculum(
            curriculum_id="full-cse-2026",
            document_id="doc-full",
            programme="B.Tech",
            branch="CSE",
            semesters=[
                Semester(semester_number=number, total_credits=20)
                for number in range(1, 9)
            ],
        )
        score = score_structured_curriculum(curriculum)
        build_mock.return_value = score
        issues_mock.return_value = (False, [], ISSUES_UNAVAILABLE_MESSAGE)

        response = analyze_curriculum_endpoint(
            "full-cse-2026", "doc-full", current_user=_DESIGNER
        )

        self.assertEqual(response.document_scope, DocumentScope.FULL_CURRICULUM)
        self.assertNotEqual(
            _check(response, "structure.semesters").status,
            CheckStatus.NOT_EVALUABLE,
        )

    @patch("backend.routers.analyzer.generate_analyzer_issues")
    @patch("backend.routers.analyzer._build_analyzer_score")
    def test_score_endpoint_never_calls_llm(self, build_mock, issues_mock):
        score = _score()
        build_mock.return_value = score
        response = score_curriculum_endpoint(
            "xyz-cse-2026", "doc-1", current_user=_DESIGNER
        )
        self.assertEqual(response.model_dump(), score.model_dump())
        issues_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
