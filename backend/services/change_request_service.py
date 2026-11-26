"""Change requests stored inside their immutable submission review history."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from pymongo import DESCENDING

from backend.data.database import get_workflow_database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _requests_for_decision(submission: Dict[str, Any], reviewer_id: str, decision: str, feedback: str, report: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = list(report.get("issues") or [])
    if not issues:
        for criterion in report.get("criteria", []):
            for check in criterion.get("checks", []):
                if check.get("status") in {"fail", "partial"}:
                    issues.append({
                        "issue_id": check.get("check_id"), "criterion": criterion.get("criterion"),
                        "related_check_ids": [check.get("check_id")],
                        "severity": "HIGH" if check.get("status") == "fail" else "MEDIUM",
                        "problem": check.get("title"), "why_it_matters": check.get("deduction_reason"),
                        "recommended_solution": f"Address {check.get('title', 'this finding')} and attach supporting evidence.",
                        "curriculum_evidence": check.get("curriculum_evidence", []),
                        "aicte_evidence": check.get("aicte_evidence", []),
                    })
    if not issues:
        issues = [{"issue_id": "reviewer-feedback", "problem": feedback, "why_it_matters": feedback,
                   "recommended_solution": feedback, "severity": "HIGH", "related_check_ids": [],
                   "curriculum_evidence": [], "aicte_evidence": []}]
    requests = []
    for issue in issues:
        severity = str(issue.get("severity", "MEDIUM"))
        requests.append({
            "request_id": str(uuid.uuid4()),
            "finding_id": issue.get("issue_id") or str(uuid.uuid4()),
            "curriculum_id": submission["curriculum_id"],
            "submission_id": submission["submission_id"],
            "curriculum_version": submission["version"],
            "reviewer_id": reviewer_id,
            "decision_type": decision,
            "issue": issue.get("problem") or issue.get("title") or feedback,
            "explanation": issue.get("why_it_matters") or feedback,
            "supporting_evidence": (issue.get("curriculum_evidence") or []) + (issue.get("aicte_evidence") or []),
            "related_check_ids": issue.get("related_check_ids", []),
            "required_corrective_action": issue.get("recommended_solution") or feedback,
            "priority": "High" if severity in {"CRITICAL", "HIGH"} else "Medium" if severity == "MEDIUM" else "Low",
            "created_at": _now(),
            "status": "Pending Designer Action" if decision == "review" else "Closed",
            "designer_response": "",
            "resubmission_submission_id": None,
        })
    return requests


def _legacy_requests(submission: Dict[str, Any], review: Dict[str, Any]) -> List[Dict[str, Any]]:
    db = get_workflow_database()
    analysis = db.submission_analyses.find_one(
        {"submission_id": submission["submission_id"]}, sort=[("created_at", DESCENDING)]
    ) or {}
    requests = _requests_for_decision(
        submission, review.get("reviewer_id", ""), review.get("decision", "review"),
        review.get("feedback", "Reviewer requested changes."), analysis.get("report", {}),
    )
    for request in requests:
        seed = f"{submission['submission_id']}:{review.get('review_id')}:{request['finding_id']}"
        request["request_id"] = f"legacy-{hashlib.sha256(seed.encode()).hexdigest()[:24]}"
        request["created_at"] = review.get("decided_at") or submission.get("submitted_at")
        request["status"] = "Closed" if review.get("decision") == "reject" else "Pending Designer Action"
    return requests


def list_change_requests(*, role: str, user_id: str) -> List[Dict[str, Any]]:
    db = get_workflow_database()
    query = {"designer_id": user_id} if role == "designer" else {}
    result = []
    for submission in db.curriculum_submissions.find(query).sort("submitted_at", DESCENDING):
        for review in submission.get("review_history", []):
            if review.get("decision") not in {"review", "reject"} and review.get("status") not in {"Revision Required", "Rejected"}:
                continue
            requests = review.get("change_requests") or _legacy_requests(submission, review)
            for request in requests:
                result.append({
                    **request,
                    "curriculum_name": submission.get("curriculum_name") or submission["curriculum_id"],
                    "review_id": review.get("review_id"),
                    "reviewer_feedback": review.get("feedback", ""),
                    "decision_date": review.get("decided_at"),
                })
        for feedback in submission.get("institution_feedback", []):
            if feedback.get("kind") != "change_request":
                continue
            result.append({
                "request_id": feedback["feedback_id"], "finding_id": feedback["feedback_id"],
                "curriculum_id": submission["curriculum_id"], "submission_id": submission["submission_id"],
                "curriculum_version": submission["version"], "reviewer_id": feedback.get("author_id"),
                "decision_type": "institute_change_request", "issue": feedback.get("category") or "Institution feedback",
                "explanation": feedback.get("observation", ""),
                "reviewer_feedback": feedback.get("observation", ""),
                "supporting_evidence": [{"excerpt": feedback.get("observation", "")}],
                "required_corrective_action": feedback.get("suggested_change", ""),
                "priority": feedback.get("priority", "Medium"), "created_at": feedback.get("created_at"),
                "decision_date": feedback.get("created_at"), "status": feedback.get("status", "Pending Designer Action"),
                "designer_response": feedback.get("designer_response", ""),
                "resubmission_submission_id": feedback.get("resubmission_submission_id"),
                "curriculum_name": submission.get("curriculum_name") or submission["curriculum_id"],
                "review_id": "institution-feedback", "source": "Institute Representative",
            })
    return result


def update_change_request(*, user_id: str, submission_id: str, review_id: str, request_id: str, status: str, response: str) -> Dict[str, Any]:
    if status not in {"In Progress", "Pending Designer Action"}:
        raise ValueError("Designer status must be In Progress or Pending Designer Action")
    if status == "In Progress" and not response.strip():
        raise ValueError("Add a response before marking this request in progress")
    db = get_workflow_database()
    submission = db.curriculum_submissions.find_one({"submission_id": submission_id, "designer_id": user_id})
    if not submission:
        raise LookupError("Change request not found")
    if review_id == "institution-feedback":
        feedback = next((item for item in submission.get("institution_feedback", []) if item.get("feedback_id") == request_id and item.get("kind") == "change_request"), None)
        if not feedback:
            raise LookupError("Change request not found")
        db.curriculum_submissions.update_one(
            {"submission_id": submission_id, "designer_id": user_id},
            {"$set": {
                "institution_feedback.$[request].status": status,
                "institution_feedback.$[request].designer_response": response.strip(),
            }},
            array_filters=[{"request.feedback_id": request_id, "request.kind": "change_request"}],
        )
        return next(row for row in list_change_requests(role="designer", user_id=user_id) if row["request_id"] == request_id)
    review = next((row for row in submission.get("review_history", []) if row.get("review_id") == review_id), None)
    if not review:
        raise LookupError("Change request not found")
    requests = review.get("change_requests") or _legacy_requests(submission, review)
    if not any(row.get("request_id") == request_id for row in requests):
        raise LookupError("Change request not found")
    if not review.get("change_requests"):
        db.curriculum_submissions.update_one(
            {"submission_id": submission_id},
            {"$set": {"review_history.$[review].change_requests": requests}},
            array_filters=[{"review.review_id": review_id}],
        )
    db.curriculum_submissions.update_one(
        {"submission_id": submission_id, "designer_id": user_id},
        {"$set": {
            "review_history.$[review].change_requests.$[request].status": status,
            "review_history.$[review].change_requests.$[request].designer_response": response.strip(),
            "review_history.$[review].change_requests.$[request].updated_at": _now(),
        }},
        array_filters=[{"review.review_id": review_id}, {"request.request_id": request_id}],
    )
    return next(row for row in list_change_requests(role="designer", user_id=user_id) if row["request_id"] == request_id)


def set_resubmission_request_status(submission: Dict[str, Any], status: str) -> None:
    db = get_workflow_database()
    db.curriculum_submissions.update_many(
        {"designer_id": submission["designer_id"], "curriculum_id": submission["curriculum_id"], "review_history.change_requests.0": {"$exists": True}},
        {"$set": {
            "review_history.$[review].change_requests.$[request].status": status,
            "review_history.$[review].change_requests.$[request].resubmission_submission_id": submission["submission_id"],
        }},
        array_filters=[{"review.status": "Revision Required"}, {"request.status": {"$in": ["Pending Designer Action", "In Progress", "Resubmitted", "Under Re-review"]}}],
    )
    db.curriculum_submissions.update_many(
        {"designer_id": submission["designer_id"], "curriculum_id": submission["curriculum_id"],
         "institution_feedback": {"$elemMatch": {"kind": "change_request", "status": {"$in": ["Pending Designer Action", "In Progress"]}}}},
        {"$set": {
            "institution_feedback.$[request].status": status,
            "institution_feedback.$[request].resubmission_submission_id": submission["submission_id"],
        }},
        array_filters=[{"request.kind": "change_request", "request.status": {"$in": ["Pending Designer Action", "In Progress"]}}],
    )


def update_requests_linked_to_submission(submission_id: str, status: str) -> None:
    db = get_workflow_database()
    db.curriculum_submissions.update_many(
        {"review_history.change_requests.resubmission_submission_id": submission_id},
        {"$set": {"review_history.$[review].change_requests.$[request].status": status}},
        array_filters=[{"review.change_requests": {"$exists": True}}, {"request.resubmission_submission_id": submission_id}],
    )
    db.curriculum_submissions.update_many(
        {"institution_feedback.resubmission_submission_id": submission_id},
        {"$set": {"institution_feedback.$[request].status": status}},
        array_filters=[{"request.resubmission_submission_id": submission_id, "request.kind": "change_request"}],
    )


def change_requests_for_decision(submission: Dict[str, Any], reviewer_id: str, decision: str, feedback: str) -> List[Dict[str, Any]]:
    db = get_workflow_database()
    analysis = db.submission_analyses.find_one(
        {"submission_id": submission["submission_id"]}, sort=[("created_at", DESCENDING)]
    ) or {}
    return _requests_for_decision(submission, reviewer_id, decision, feedback, analysis.get("report", {}))
