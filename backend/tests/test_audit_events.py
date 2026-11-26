import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.services.workflow_service import list_audit_events


class AuditEventTests(unittest.TestCase):
    def test_event_feed_is_derived_from_stored_submission_review_and_publication_history(self):
        submitted_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        decided_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        published_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = [{
            "submission_id": "sub-1", "curriculum_id": "cse", "curriculum_name": "CSE",
            "version": 2, "institute_id": "inst-1", "institute_representative_id": "ir-1",
            "submitted_at": submitted_at,
            "review_history": [{"review_id": "review-1", "reviewer_id": "reviewer-1", "status": "Accepted", "decided_at": decided_at, "feedback": "Accepted."}],
            "workflow_history": [{"event": "Published", "actor_id": "ir-1", "created_at": published_at}],
        }]
        db = SimpleNamespace(
            curriculum_submissions=SimpleNamespace(find=MagicMock(return_value=cursor)),
            institutions=SimpleNamespace(find_one=MagicMock(return_value={"name": "Example Institute"})),
            users=SimpleNamespace(find=MagicMock(return_value=[
                {"user_id": "ir-1", "name": "Representative"},
                {"user_id": "reviewer-1", "name": "Reviewer"},
            ])),
        )
        with patch("backend.services.workflow_service.get_workflow_database", return_value=db):
            events = list_audit_events()
        self.assertEqual([event["action"] for event in events], ["Published", "Accepted", "Submission created"])
        self.assertEqual(events[1]["actor_name"], "Reviewer")
        self.assertTrue(all(event["submission_id"] == "sub-1" for event in events))
        self.assertTrue(all("password" not in event for event in events))


if __name__ == "__main__":
    unittest.main()
