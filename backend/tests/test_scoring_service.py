import unittest
from unittest.mock import patch

from backend.core.auth import AuthenticatedUser
from backend.routers.analyzer import score_curriculum_endpoint
from backend.models.analyzer_schemas import (
    Course,
    EvidenceReference,
    Semester,
    StructuredCurriculum,
)
from backend.models.analyzer_scoring_schemas import CheckStatus, DocumentScope
from backend.services.aicte_evidence_service import enrich_score_with_aicte_evidence
from backend.services.scoring_service import score_structured_curriculum


_DESIGNER = AuthenticatedUser(user_id="designer-a", role="designer")


def _evidence(excerpt: str = "Extracted curriculum row") -> EvidenceReference:
    return EvidenceReference(
        page_number=4,
        chunk_index=12,
        excerpt=excerpt,
        fields=["course_title", "credits"],
    )


def _course(title: str, **values) -> Course:
    defaults = {"course_title": title, "evidence": [_evidence(title)]}
    defaults.update(values)
    return Course(**defaults)


def _curriculum(**values) -> StructuredCurriculum:
    defaults = {
        "curriculum_id": "xyz-cse-2026",
        "document_id": "doc-1",
        "programme": "B.Tech",
        "branch": "CSE",
    }
    defaults.update(values)
    return StructuredCurriculum(**defaults)


def _check(score, check_id):
    return next(
        check
        for criterion in score.criteria
        for check in criterion.checks
        if check.check_id == check_id
    )


def _criterion(score, criterion_id):
    return next(item for item in score.criteria if item.criterion == criterion_id)


class FakeAicteCollection:
    def __init__(self, records):
        self.records = records
        self.last_query = None

    def find(self, query, projection):
        self.last_query = query
        return list(self.records)


class ScoringServiceTests(unittest.TestCase):
    def test_detects_partial_and_full_curriculum_scope(self):
        partial = score_structured_curriculum(
            _curriculum(
                total_credits=25,
                semesters=[Semester(semester_number=5, total_credits=25)],
            )
        )
        self.assertEqual(
            partial.document_scope,
            DocumentScope.PARTIAL_CURRICULUM,
        )
        self.assertEqual(
            partial.scope_reason,
            "Only Semester 5 was reliably extracted.",
        )

        full = score_structured_curriculum(
            _curriculum(
                semesters=[
                    Semester(semester_number=number, total_credits=20)
                    for number in range(1, 9)
                ]
            )
        )
        self.assertEqual(full.document_scope, DocumentScope.FULL_CURRICULUM)

    def test_partial_scope_excludes_full_program_checks_but_keeps_local_checks(self):
        machine_learning = _course(
            "Machine Learning",
            lecture_hours=3,
            tutorial_hours=0,
            practical_hours=1,
            credits=4,
            topics=["Applied machine learning and cloud deployment"],
            course_outcomes=["Design and evaluate machine-learning models"],
        )
        internship = _course("Summer Internship", credits=6)
        score = score_structured_curriculum(
            _curriculum(
                total_credits=25,
                semesters=[
                    Semester(
                        semester_number=5,
                        total_credits=25,
                        evidence=[_evidence("Semester 5 total: 25")],
                    )
                ],
                courses=[machine_learning],
                internships=[internship],
            )
        )

        for check_id in (
            "structure.semesters",
            "structure.total_credits",
            "structure.category_distribution",
            "structure.professional_core",
            "structure.professional_elective",
            "structure.open_elective",
            "structure.project_internship",
            "compliance.induction",
            "compliance.environment",
            "compliance.constitution_ikt",
            "compliance.human_values",
            "compliance.mandatory_non_credit",
            "compliance.essential_core",
            "skills.machine_learning_data",
            "skills.projects_practical",
        ):
            check = _check(score, check_id)
            self.assertEqual(check.status, CheckStatus.NOT_EVALUABLE)
            self.assertEqual(
                check.deduction_reason,
                "Not evaluable from a partial curriculum document.",
            )

        for check_id in (
            "structure.semester_distribution",
            "structure.ltp_balance",
            "compliance.internship",
            "industry.machine_learning",
        ):
            self.assertEqual(_check(score, check_id).status, CheckStatus.PASS)

        observed_skill = _check(score, "skills.machine_learning_data")
        self.assertIn("Machine Learning", observed_skill.actual)

    def test_project_detection_requires_title_category_or_explicit_record(self):
        machine_learning = _course(
            "Machine Learning",
            topics=[
                "Project-based application development with practical model evaluation"
            ],
        )
        full_score = score_structured_curriculum(
            _curriculum(total_credits=163, courses=[machine_learning])
        )
        self.assertEqual(
            _check(full_score, "compliance.project").status,
            CheckStatus.FAIL,
        )
        self.assertEqual(
            _check(full_score, "industry.projects").status,
            CheckStatus.FAIL,
        )
        self.assertNotIn(
            "Machine Learning",
            _check(full_score, "compliance.project").actual,
        )

        explicit_project = _course("Major Project", credits=8)
        project_score = score_structured_curriculum(
            _curriculum(
                total_credits=25,
                semesters=[Semester(semester_number=5, total_credits=25)],
                courses=[explicit_project],
            )
        )
        self.assertEqual(
            _check(project_score, "compliance.project").status,
            CheckStatus.PASS,
        )

    def test_partial_scope_renormalizes_structure_denominator(self):
        score = score_structured_curriculum(
            _curriculum(
                total_credits=25,
                semesters=[Semester(semester_number=5, total_credits=25)],
                courses=[
                    _course(
                        "Operating Systems",
                        lecture_hours=3,
                        tutorial_hours=0,
                        practical_hours=1,
                    )
                ],
            )
        )
        structure = _criterion(score, "structure")
        evaluable = [
            check for check in structure.checks if check.obtained_marks is not None
        ]
        self.assertEqual(
            [check.check_id for check in evaluable],
            ["structure.semester_distribution", "structure.ltp_balance"],
        )
        self.assertEqual(structure.evaluable_maximum_marks, 15)
        self.assertEqual(structure.score, 100)
        evaluable_criteria = [
            criterion for criterion in score.criteria if criterion.score is not None
        ]
        expected_overall = round(
            sum(
                criterion.score * criterion.weight
                for criterion in evaluable_criteria
            )
            / sum(criterion.weight for criterion in evaluable_criteria),
            2,
        )
        self.assertEqual(score.overall_score, expected_overall)
        self.assertEqual(
            score.evaluable_weight,
            sum(criterion.weight for criterion in evaluable_criteria),
        )

    def test_exact_credit_match_passes(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        check = _check(score, "structure.total_credits")
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(check.obtained_marks, check.maximum_marks)

    def test_credit_tolerance_allows_minor_variation(self):
        score = score_structured_curriculum(_curriculum(total_credits=160))
        self.assertEqual(
            _check(score, "structure.total_credits").status,
            CheckStatus.PASS,
        )

    def test_intermediate_credit_difference_is_partial(self):
        score = score_structured_curriculum(_curriculum(total_credits=150))
        check = _check(score, "structure.total_credits")
        self.assertEqual(check.status, CheckStatus.PARTIAL)
        self.assertGreater(check.obtained_marks, 0)
        self.assertLess(check.obtained_marks, check.maximum_marks)

    def test_large_credit_difference_fails(self):
        score = score_structured_curriculum(_curriculum(total_credits=130))
        check = _check(score, "structure.total_credits")
        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(check.obtained_marks, 0)

    def test_missing_credit_total_is_not_evaluable(self):
        score = score_structured_curriculum(_curriculum())
        check = _check(score, "structure.total_credits")
        self.assertEqual(check.status, CheckStatus.NOT_EVALUABLE)
        self.assertIsNone(check.obtained_marks)

    def test_eight_semesters_pass(self):
        semesters = [
            Semester(semester_number=number, total_credits=20, evidence=[_evidence()])
            for number in range(1, 9)
        ]
        score = score_structured_curriculum(_curriculum(semesters=semesters))
        self.assertEqual(_check(score, "structure.semesters").status, CheckStatus.PASS)

    def test_exact_category_distribution_passes(self):
        courses = [
            _course("Humanities", category="HSMC", credits=16),
            _course("Basic Science", category="BSC", credits=23),
            _course("Engineering Science", category="ESC", credits=29),
            _course("Professional Core", category="PCC", credits=59),
            _course("Professional Elective", category="PEC", credits=12),
            _course("Open Elective", category="OEC", credits=9),
        ]
        score = score_structured_curriculum(
            _curriculum(total_credits=163, courses=courses)
        )
        for check_id in (
            "structure.category_distribution",
            "structure.professional_core",
            "structure.professional_elective",
            "structure.open_elective",
        ):
            self.assertEqual(_check(score, check_id).status, CheckStatus.PASS)

    def test_database_alias_matches_core_skill(self):
        score = score_structured_curriculum(
            _curriculum(
                total_credits=163,
                courses=[_course("Database Management Systems")],
            )
        )
        check = _check(score, "skills.databases")
        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertIn("Database Management Systems", check.actual)

    def test_missing_outcomes_are_not_evaluable(self):
        score = score_structured_curriculum(
            _curriculum(courses=[_course("Operating Systems")])
        )
        self.assertEqual(
            _check(score, "outcomes.course_coverage").status,
            CheckStatus.NOT_EVALUABLE,
        )

    def test_missing_assessment_is_not_evaluable(self):
        score = score_structured_curriculum(
            _curriculum(courses=[_course("Operating Systems", practical_hours=2)])
        )
        for check in _criterion(score, "assessment").checks:
            self.assertEqual(check.status, CheckStatus.NOT_EVALUABLE)

    def test_assessment_checks_detect_theory_and_practical(self):
        course = _course(
            "Programming Laboratory",
            practical_hours=2,
            assessment_information=["Written examination, practical test and viva"],
        )
        score = score_structured_curriculum(_curriculum(courses=[course]))
        self.assertEqual(
            _check(score, "assessment.theory_practical").status,
            CheckStatus.PASS,
        )
        self.assertEqual(
            _check(score, "assessment.practical_alignment").status,
            CheckStatus.PASS,
        )

    def test_mandatory_zero_credit_component_passes(self):
        course = _course("Environmental Sciences", category="MC", credits=0)
        score = score_structured_curriculum(
            _curriculum(total_credits=163, mandatory_courses=[course])
        )
        self.assertEqual(
            _check(score, "compliance.mandatory_non_credit").status,
            CheckStatus.PASS,
        )

    def test_resource_detection(self):
        course = _course(
            "Machine Learning Laboratory",
            practical_hours=2,
            topics=["Experiments using Python software tools and datasets"],
            references=["NPTEL Machine Learning course"],
        )
        score = score_structured_curriculum(_curriculum(courses=[course]))
        self.assertEqual(_check(score, "resources.online_learning").status, CheckStatus.PASS)
        self.assertEqual(_check(score, "resources.labs_practicals").status, CheckStatus.PASS)

    def test_skill_taxonomy_covers_aliases_and_practical_records(self):
        courses = [
            _course("Introduction to Database Systems"),
            _course("Formal Languages and Automata Theory"),
            _course("Computer Organization"),
            _course("Network Protocols"),
            _course("Python Programming Lab", practical_hours=2),
        ]
        score = score_structured_curriculum(
            _curriculum(total_credits=163, courses=courses)
        )
        for check_id in (
            "skills.databases",
            "skills.theory_computation",
            "skills.computer_architecture",
            "skills.computer_networks",
            "skills.programming",
            "skills.projects_practical",
        ):
            self.assertEqual(_check(score, check_id).status, CheckStatus.PASS)

    def test_criterion_score_uses_only_evaluable_check_denominator(self):
        score = score_structured_curriculum(_curriculum(total_credits=150))
        structure = _criterion(score, "structure")
        evaluable = [check for check in structure.checks if check.obtained_marks is not None]
        expected = round(
            sum(check.obtained_marks for check in evaluable)
            / sum(check.maximum_marks for check in evaluable)
            * 100,
            2,
        )
        self.assertEqual(structure.score, expected)
        self.assertEqual(structure.evaluable_maximum_marks, 15)
        self.assertEqual(structure.evaluation_coverage, 15)
        self.assertTrue(structure.low_coverage)

    def test_overall_score_renormalizes_evaluable_criterion_weights(self):
        courses = [
            _course("Database Management Systems"),
            _course("Operating Systems"),
        ]
        score = score_structured_curriculum(
            _curriculum(total_credits=163, courses=courses)
        )
        evaluable = [item for item in score.criteria if item.score is not None]
        expected = round(
            sum(item.score * item.weight for item in evaluable)
            / sum(item.weight for item in evaluable),
            2,
        )
        self.assertEqual(score.overall_score, expected)
        self.assertEqual(score.evaluable_weight, sum(item.weight for item in evaluable))

    def test_overall_evaluation_coverage_is_weighted(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        # Only the 15-mark Structure credit check is evaluable. Structure has
        # a 20% overall weight, so supported overall weight is 15% * 20% = 3%.
        self.assertEqual(score.overall_evaluation_coverage, 3)
        self.assertTrue(score.low_coverage)

    def test_aicte_model_values_are_not_classified_as_mandatory(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        self.assertEqual(
            _check(score, "structure.total_credits").rule_type.value,
            "AICTE_MODEL_REFERENCE",
        )

    def test_curriculum_evidence_does_not_create_fallback_aicte_evidence(self):
        score = score_structured_curriculum(
            _curriculum(
                total_credits=163,
                evidence=[_evidence("Curriculum total: 163 credits")],
            )
        )
        check = _check(score, "structure.total_credits")
        self.assertEqual(check.curriculum_evidence[0].page_number, 4)
        self.assertEqual(check.curriculum_evidence[0].chunk_index, 12)
        self.assertEqual(check.aicte_evidence, [])

    def test_legacy_aicte_evidence_retrieval_preserves_missing_locations(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        collection = FakeAicteCollection(
            [
                {
                    "text": "General Course Structure and Range of Credits: 163 credits",
                    "metadata": {"source": "Updated-AICTE - UG CSE.pdf"},
                }
            ]
        )
        enriched = enrich_score_with_aicte_evidence(score, collection=collection)
        evidence = _check(enriched, "structure.total_credits").aicte_evidence[0]
        self.assertTrue(enriched.aicte_reference_available)
        self.assertEqual(evidence.source, "Updated-AICTE - UG CSE.pdf")
        self.assertIsNone(evidence.page_number)
        self.assertIsNone(evidence.chunk_index)
        self.assertIn("163 credits", evidence.excerpt)

    def test_missing_aicte_document_excludes_reference_checks_and_overall_score(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        enriched = enrich_score_with_aicte_evidence(
            score,
            collection=FakeAicteCollection([]),
        )
        check = _check(enriched, "structure.total_credits")
        self.assertFalse(enriched.aicte_reference_available)
        self.assertIsNone(enriched.overall_score)
        self.assertEqual(check.status, CheckStatus.NOT_EVALUABLE)
        self.assertIsNone(check.obtained_marks)
        self.assertEqual(check.aicte_evidence, [])
        self.assertIn("Official AICTE reference", check.deduction_reason)

    def test_uploaded_reference_without_check_evidence_is_conservative(self):
        score = score_structured_curriculum(_curriculum(total_credits=163))
        enriched = enrich_score_with_aicte_evidence(
            score,
            collection=FakeAicteCollection(
                [{"text": "Student induction programme", "source": "official.pdf"}]
            ),
        )
        self.assertTrue(enriched.aicte_reference_available)
        self.assertEqual(
            _check(enriched, "structure.total_credits").status,
            CheckStatus.NOT_EVALUABLE,
        )
        self.assertTrue(
            _check(enriched, "compliance.induction").aicte_evidence
        )

    def test_aicte_evidence_enrichment_does_not_change_scores(self):
        score = score_structured_curriculum(_curriculum(total_credits=150))
        enriched = enrich_score_with_aicte_evidence(
            score,
            collection=FakeAicteCollection(
                [
                    {
                        "text": "Professional Core Courses 59 credits. Total 163 credits.",
                        "source": "Updated-AICTE - UG CSE.pdf",
                    }
                ]
            ),
        )
        self.assertEqual(enriched.overall_score, score.overall_score)
        self.assertEqual(
            [item.score for item in enriched.criteria],
            [item.score for item in score.criteria],
        )
        self.assertEqual(
            [check.obtained_marks for item in enriched.criteria for check in item.checks],
            [check.obtained_marks for item in score.criteria for check in item.checks],
        )

    def test_repeatability(self):
        curriculum = _curriculum(
            total_credits=163,
            courses=[
                _course(
                    "Database Management Systems",
                    practical_hours=2,
                    course_outcomes=["Design and implement a relational database"],
                    assessment_information=["Written exam and practical viva"],
                    references=["NPTEL Database Systems"],
                )
            ],
        )
        first = score_structured_curriculum(curriculum)
        second = score_structured_curriculum(curriculum)
        self.assertEqual(first.model_dump(), second.model_dump())

    @patch("backend.routers.analyzer.enrich_score_with_aicte_evidence", side_effect=lambda score: score)
    @patch("backend.routers.analyzer.extract_structured_curriculum")
    def test_scoring_endpoint_reuses_phase_two_extraction(
        self,
        extract_mock,
        evidence_mock,
    ):
        extract_mock.return_value = _curriculum(total_credits=163)
        response = score_curriculum_endpoint(
            "xyz-cse-2026",
            document_id="doc-1",
            current_user=_DESIGNER,
        )
        extract_mock.assert_called_once_with(
            curriculum_id="xyz-cse-2026",
            document_id="doc-1",
            owner_id="designer-a",
        )
        self.assertEqual(response.curriculum_id, "xyz-cse-2026")
        self.assertEqual(response.scoring_version, "cse_v1")
        evidence_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
