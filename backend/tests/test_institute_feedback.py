import unittest
from unittest.mock import Mock, patch

from backend.services.workflow_service import record_institute_feedback
from backend.services.change_request_service import list_change_requests


class Cursor(list):
    def sort(self, *_args, **_kwargs):
        return self


class InstituteFeedbackTests(unittest.TestCase):
    def test_change_request_is_embedded_on_the_published_version(self):
        published = {
            "submission_id": "sub-1", "curriculum_id": "cse", "version": 2,
            "designer_id": "designer-1", "institute_id": "inst-1", "status": "Published",
        }
        collection = Mock()
        collection.find_one.return_value = published
        collection.find_one_and_update.return_value = {**published, "institution_feedback": [{"feedback_id": "feedback-1"}]}
        db = type("DB", (), {"curriculum_submissions": collection})()
        with patch("backend.services.workflow_service.get_workflow_database", return_value=db), patch(
            "backend.services.workflow_service.notify_user"
        ):
            result = record_institute_feedback(
                submission_id="sub-1", institute_id="inst-1", author_id="rep-1",
                kind="change_request", category="Assessment", observation="Need delivery evidence.",
                suggested_change="Add a lab assessment.", priority="High",
            )
        query, update = collection.find_one_and_update.call_args.args[:2]
        self.assertEqual(query, {"submission_id": "sub-1", "institute_id": "inst-1", "status": "Published"})
        entry = update["$push"]["institution_feedback"]
        self.assertEqual(entry["curriculum_id"], "cse")
        self.assertEqual(entry["curriculum_version"], 2)
        self.assertEqual(entry["status"], "Pending Designer Action")
        self.assertEqual(result["feedback_id"], "feedback-1")

    def test_unpublished_or_other_institution_curriculum_cannot_receive_feedback(self):
        collection = Mock()
        collection.find_one.return_value = None
        db = type("DB", (), {"curriculum_submissions": collection})()
        with patch("backend.services.workflow_service.get_workflow_database", return_value=db):
            with self.assertRaises(LookupError):
                record_institute_feedback(
                    submission_id="sub-1", institute_id="inst-other", author_id="rep-1",
                    kind="feedback", category="Delivery", observation="Observed issue.",
                )
        collection.find_one_and_update.assert_not_called()

    def test_designer_change_request_feed_reads_institution_feedback(self):
        collection = Mock()
        collection.find.return_value = Cursor([{
            "submission_id": "sub-1", "designer_id": "designer-1", "curriculum_id": "cse",
            "curriculum_name": "B.Tech CSE", "version": 2, "review_history": [],
            "institution_feedback": [{
                "feedback_id": "feedback-1", "kind": "change_request", "category": "Assessment",
                "observation": "Add better evidence.", "suggested_change": "Include a lab.",
                "status": "Pending Designer Action", "curriculum_version": 2,
            }],
        }])
        db = type("DB", (), {"curriculum_submissions": collection})()
        with patch("backend.services.change_request_service.get_workflow_database", return_value=db):
            rows = list_change_requests(role="designer", user_id="designer-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["request_id"], "feedback-1")
        self.assertEqual(rows[0]["source"], "Institute Representative")
        self.assertEqual(rows[0]["required_corrective_action"], "Include a lab.")


if __name__ == "__main__":
    unittest.main()
