import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bson import ObjectId
from fastapi.testclient import TestClient

import main
from backend.core.auth import AuthenticatedUser, require_authenticated_user
from backend.services.workflow_service import create_institution, decide_submission, publish_submission


class SubmissionWorkflowApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)

    def authenticate(self, user_id, role):
        main.app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(user_id, role)

    def test_reviewer_queue_is_role_protected_and_database_backed(self):
        self.authenticate("designer-a", "designer")
        denied = self.client.get("/api/workflow/submissions")
        self.assertEqual(denied.status_code, 403)

        self.authenticate("reviewer-a", "reviewer")
        rows = [{"submission_id": "sub-1", "status": "Pending", "version": 1}]
        with patch("backend.routers.workflow.list_pending_submissions", return_value=rows) as queue_mock:
            response = self.client.get("/api/workflow/submissions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), rows)
        queue_mock.assert_called_once_with()

    def test_admin_activity_feed_is_protected_and_reads_stored_workflow_events(self):
        self.authenticate("reviewer-a", "reviewer")
        denied = self.client.get("/api/workflow/admin/audit-events")
        self.assertEqual(denied.status_code, 403)

        self.authenticate("admin-a", "admin")
        events = [{"event_id": "sub-1:review-1", "action": "Revision Required", "submission_id": "sub-1"}]
        with patch("backend.routers.workflow.list_audit_events", return_value=events) as audit_mock:
            response = self.client.get("/api/workflow/admin/audit-events")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), events)
        audit_mock.assert_called_once_with()

    def test_account_profile_and_preferences_are_scoped_to_authenticated_user(self):
        self.authenticate("designer-a", "designer")
        profile = {"user_id": "designer-a", "name": "Designer", "preferences": {"timezone": "Asia/Kolkata"}}
        with patch("backend.routers.workflow.get_account_profile", return_value=profile) as profile_mock:
            response = self.client.get("/api/workflow/account/me")
        self.assertEqual(response.status_code, 200)
        profile_mock.assert_called_once_with("designer-a")

        with patch("backend.routers.workflow.update_account_preferences", return_value=profile) as update_mock:
            response = self.client.patch("/api/workflow/account/me/preferences", json={"timezone": "Asia/Kolkata"})
        self.assertEqual(response.status_code, 200)
        update_mock.assert_called_once_with("designer-a", {"timezone": "Asia/Kolkata"})

        invalid = self.client.patch("/api/workflow/account/me/preferences", json={"role": "admin"})
        self.assertEqual(invalid.status_code, 422)

    def test_published_course_structure_is_limited_to_the_institute(self):
        self.authenticate("rep-a", "institute")
        record = {"submission_id": "sub-other", "status": "Published", "institute_id": "inst-b"}
        with (
            patch("backend.routers.workflow._actor", return_value={"user_id": "rep-a", "role": "institute", "institute_id": "inst-a"}),
            patch("backend.routers.workflow.find_submission", return_value=record),
            patch("backend.routers.workflow.extract_structured_curriculum") as extract_mock,
        ):
            response = self.client.get("/api/workflow/publications/sub-other/curriculum")
        self.assertEqual(response.status_code, 404)
        extract_mock.assert_not_called()

        self.authenticate("designer-a", "designer")
        denied = self.client.get("/api/workflow/publications/sub-other/curriculum")
        self.assertEqual(denied.status_code, 403)

    def test_analyzer_criteria_are_role_protected_and_use_configured_definitions(self):
        self.authenticate("designer-a", "designer")
        self.assertEqual(self.client.get("/api/analyzer/criteria").status_code, 403)
        self.authenticate("reviewer-a", "reviewer")
        response = self.client.get("/api/analyzer/criteria")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())
        self.assertIn("availability_policy", response.json()[0])

    def test_institute_submission_upload_uses_authorized_prepared_document(self):
        self.authenticate("rep-a", "institute")
        prepared = {"_id": ObjectId(), "owner_id": "designer-a", "curriculum_id": "cse", "filename": "CSE.pdf", "programme": "B.Tech", "branch": "CSE", "year": 2026, "handoff_status": "Ready for institute", "original_file_id": ObjectId()}
        reserved = {"submission_id": "sub-1", "version": 1}
        result = {"submission_id": "sub-1", "version": 1, "status": "Pending"}
        with (
            patch("backend.routers.workflow._actor", return_value={"user_id": "rep-a", "role": "institute", "institute_id": "inst-a"}),
            patch("backend.routers.workflow.get_prepared_metadata", return_value=prepared) as prepared_mock,
            patch("backend.routers.workflow.read_original_pdf", return_value=(b"%PDF content", "CSE.pdf")),
            patch("backend.routers.workflow.reserve_submission", return_value=reserved),
            patch("backend.routers.workflow.extract_pages_from_pdf", return_value=[object()]),
            patch("backend.routers.workflow.combine_pdf_pages", return_value="indexed text"),
            patch("backend.routers.workflow.process_and_store_pdf", return_value=(1, False)) as index_mock,
            patch("backend.routers.workflow.store_original_pdf", return_value=ObjectId()) as file_mock,
            patch("backend.routers.workflow.finalize_submission", return_value=result) as finalize_mock,
        ):
            response = self.client.post(
                "/api/workflow/submissions",
                data={"curriculum_id": "cse", "document_id": "prepared-doc", "curriculum_name": "B.Tech CSE"},
                files={"file": ("submitted.pdf", b"%PDF content", "application/pdf")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)
        self.assertEqual(prepared_mock.call_args.args[1:], ("cse", "prepared-doc"))
        self.assertEqual(index_mock.call_args.kwargs["owner_id"], "designer-a")
        self.assertEqual(index_mock.call_args.kwargs["source_type"], "submitted_curriculum")
        self.assertTrue(index_mock.call_args.args[1].startswith("submission-sub-1"))
        self.assertEqual(file_mock.call_args.args[1], "submitted.pdf")
        self.assertEqual(finalize_mock.call_args.args[0], "sub-1")

    def test_designer_can_send_owned_curriculum_to_institute(self):
        self.authenticate("designer-a", "designer")
        record = {"document_id": "doc-1", "handoff_status": "Ready for institute"}
        with patch("backend.routers.workflow._actor", return_value={"user_id": "designer-a", "role": "designer", "institute_id": "inst-a"}), patch("backend.routers.workflow.handoff_curriculum", return_value=record) as handoff_mock:
            response = self.client.post("/api/workflow/curricula/doc-1/handoff")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), record)
        handoff_mock.assert_called_once_with(designer_id="designer-a", document_id="doc-1")

    def test_institute_submits_the_exact_handed_off_pdf_without_reupload(self):
        self.authenticate("rep-a", "institute")
        file_id = ObjectId()
        prepared = {
            "_id": ObjectId(), "owner_id": "designer-a", "curriculum_id": "cse",
            "document_id": "prepared-doc", "filename": "CSE.pdf",
            "handoff_status": "Ready for institute", "original_file_id": file_id,
        }
        result = {"submission_id": "sub-2", "version": 1, "status": "Pending"}
        with (
            patch("backend.routers.workflow._actor", return_value={"user_id": "rep-a", "role": "institute", "institute_id": "inst-a"}),
            patch("backend.routers.workflow.get_prepared_metadata", return_value=prepared),
            patch("backend.routers.workflow.reserve_submission", return_value={"submission_id": "sub-2"}) as reserve_mock,
            patch("backend.routers.workflow.finalize_submission", return_value=result) as finalize_mock,
        ):
            response = self.client.post("/api/workflow/submissions/prepared", json={"curriculum_id": "cse", "document_id": "prepared-doc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)
        reserve_mock.assert_called_once()
        finalize_mock.assert_called_once_with("sub-2", document_id="prepared-doc", filename="CSE.pdf", file_id=file_id)

    def test_publication_requires_an_accepted_institution_submission(self):
        self.authenticate("rep-a", "institute")
        published = {
            "submission_id": "sub-3", "curriculum_id": "cse", "curriculum_name": "CSE",
            "designer_id": "designer-a", "institute_representative_id": "rep-a", "institute_id": "inst-a",
            "document_id": "doc-3", "document_filename": "cse.pdf", "version": 1,
            "submitted_at": "2026-01-01T00:00:00Z", "status": "Published", "review_history": [],
        }
        with (
            patch("backend.routers.workflow._actor", return_value={"user_id": "rep-a", "role": "institute", "institute_id": "inst-a"}),
            patch("backend.routers.workflow.publish_submission", return_value=published) as publish_mock,
        ):
            response = self.client.post("/api/workflow/submissions/sub-3/publish")
        self.assertEqual(response.status_code, 200)
        publish_mock.assert_called_once_with(submission_id="sub-3", institute_id="inst-a", publisher_id="rep-a")

        self.authenticate("designer-a", "designer")
        denied = self.client.post("/api/workflow/submissions/sub-3/publish")
        self.assertEqual(denied.status_code, 403)

    def test_publish_submission_transitions_only_accepted_record(self):
        collection = Mock()
        collection.find_one_and_update.return_value = {
            "submission_id": "sub-3", "curriculum_id": "cse", "curriculum_name": "CSE",
            "designer_id": "designer-a", "institute_representative_id": "rep-a", "institute_id": "inst-a",
            "document_id": "doc-3", "document_filename": "cse.pdf", "version": 1,
            "submitted_at": "2026-01-01T00:00:00Z", "status": "Published", "review_history": [],
        }
        db = SimpleNamespace(curriculum_submissions=collection)
        with patch("backend.services.workflow_service.ensure_workflow_indexes"), patch(
            "backend.services.workflow_service.get_workflow_database", return_value=db
        ), patch("backend.services.workflow_service.notify_user"):
            result = publish_submission(submission_id="sub-3", institute_id="inst-a", publisher_id="rep-a")
        query, update = collection.find_one_and_update.call_args.args[:2]
        self.assertEqual(query, {"submission_id": "sub-3", "institute_id": "inst-a", "status": "Accepted"})
        self.assertEqual(update["$set"]["status"], "Published")
        self.assertEqual(result["status"], "Published")

    def test_reviewers_can_download_submitted_pdf_but_other_designers_cannot(self):
        record = {"submission_id": "sub-1", "status": "Pending", "original_file_id": ObjectId(), "designer_id": "designer-a", "institute_id": "inst-a"}
        with patch("backend.routers.workflow._submission", return_value=record), patch("backend.routers.workflow.read_original_pdf", return_value=(b"%PDF content", "curriculum.pdf")) as read_mock:
            self.authenticate("designer-b", "designer")
            with patch("backend.routers.workflow._actor", return_value={"user_id": "designer-b", "role": "designer", "institute_id": "inst-a"}):
                denied = self.client.get("/api/workflow/submissions/sub-1/document")
            self.assertEqual(denied.status_code, 404)
            read_mock.assert_not_called()

            self.authenticate("reviewer-a", "reviewer")
            with patch("backend.routers.workflow._actor", return_value={"user_id": "reviewer-a", "role": "reviewer"}):
                response = self.client.get("/api/workflow/submissions/sub-1/document")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"%PDF content")
            self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_decision_transition_is_atomic_and_feedback_is_required(self):
        collection = Mock()
        collection.find_one.return_value = {
            "submission_id": "sub-1", "curriculum_id": "cse", "curriculum_name": "CSE",
            "designer_id": "designer-a", "institute_representative_id": "rep-a",
            "institute_id": "inst-a", "version": 1,
        }
        collection.find_one_and_update.return_value = {
            "submission_id": "sub-1", "curriculum_id": "cse", "curriculum_name": "CSE",
            "designer_id": "designer-a", "institute_representative_id": "rep-a",
            "institute_id": "inst-a", "document_id": "doc-1", "document_filename": "submission.pdf",
            "version": 1, "submitted_at": "2026-01-01T00:00:00Z", "status": "Revision Required", "review_history": [],
        }
        db = SimpleNamespace(curriculum_submissions=collection)
        with patch("backend.services.workflow_service.ensure_workflow_indexes"), patch("backend.services.workflow_service.get_workflow_database", return_value=db), patch("backend.services.workflow_service.notify_user"), patch("backend.services.change_request_service.change_requests_for_decision", return_value=[]):
            with self.assertRaises(ValueError):
                decide_submission(submission_id="sub-1", reviewer_id="reviewer-a", decision="reject", feedback=" ")
            collection.find_one_and_update.assert_not_called()
            decide_submission(submission_id="sub-1", reviewer_id="reviewer-a", decision="review", feedback="Add assessment evidence")
        query, update = collection.find_one_and_update.call_args.args[:2]
        self.assertEqual(query, {"submission_id": "sub-1", "status": "Pending"})
        self.assertEqual(update["$set"]["status"], "Revision Required")
        self.assertEqual(update["$push"]["review_history"]["feedback"], "Add assessment evidence")

    def test_institution_response_omits_internal_mongo_object_id(self):
        collection = Mock()
        collection.insert_one.side_effect = lambda record: record.update({"_id": ObjectId()})
        db = SimpleNamespace(institutions=collection)
        with patch("backend.services.workflow_service.ensure_workflow_indexes"), patch("backend.services.workflow_service.get_workflow_database", return_value=db):
            response = create_institution("Example Institute")
        self.assertNotIn("_id", response)
        self.assertNotIn("name_key", response)
        self.assertEqual(response["name"], "Example Institute")


if __name__ == "__main__":
    unittest.main()
