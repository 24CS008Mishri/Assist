import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.services.workflow_service import record_analysis


class Cursor(list):
    def sort(self, *_args, **_kwargs):
        return self


class FindingHistoryTests(unittest.TestCase):
    def snapshot_for(self, current_status):
        submissions = Mock()
        submissions.find.return_value = Cursor([{"submission_id": "v1", "version": 1}])
        analyses = Mock()
        analyses.find.return_value = Cursor([{
            "submission_id": "v1", "version": 1,
            "finding_snapshot": [{
                "finding_id": "check-x", "original_issue": "Missing topic",
                "status": "Open", "first_detected_version": 1,
                "curriculum_evidence": [],
            }],
        }])
        db = SimpleNamespace(
            curriculum_submissions=submissions,
            submission_analyses=analyses,
        )
        submission = {
            "submission_id": "v2", "designer_id": "designer-1",
            "curriculum_id": "cse", "version": 2, "document_id": "doc-v2",
        }
        report = {
            "overall_score": 80,
            "criteria": [{"criterion": "coverage", "checks": [{
                "check_id": "check-x", "title": "Missing topic",
                "status": current_status, "curriculum_evidence": [],
            }]}],
        }
        with patch("backend.services.workflow_service.ensure_workflow_indexes"), patch(
            "backend.services.workflow_service.get_workflow_database", return_value=db
        ):
            record_analysis(submission, "reviewer-1", report)
        return analyses.insert_one.call_args.args[0]["finding_snapshot"][0]

    def test_unevaluable_finding_stays_open(self):
        finding = self.snapshot_for("not_evaluable")
        self.assertEqual(finding["status"], "Open")
        self.assertNotIn("resolved_in_version", finding)

    def test_passing_finding_is_resolved_with_version_reference(self):
        finding = self.snapshot_for("pass")
        self.assertEqual(finding["status"], "Resolved")
        self.assertEqual(finding["resolved_in_version"], 2)


if __name__ == "__main__":
    unittest.main()
