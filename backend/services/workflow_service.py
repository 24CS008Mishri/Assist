"""MongoDB-backed identity, submission, file and review workflow services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.data.database import get_workflow_database


ROLES = {"admin", "designer", "reviewer", "institute"}
_HASH_ROUNDS = 310_000


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def notify_user(user_id: str, title: str, message: str, submission_id: str) -> None:
    """Keep workflow notices on the existing user identity document."""
    notice = {
        "notification_id": str(uuid.uuid4()), "title": title,
        "message": message, "submission_id": submission_id,
        "created_at": now_utc(), "read": False,
    }
    get_workflow_database().users.update_one(
        {"user_id": user_id},
        {"$push": {"notifications": {"$each": [notice], "$slice": -50}}},
    )


def list_user_notifications(user_id: str) -> List[Dict[str, Any]]:
    user = get_workflow_database().users.find_one({"user_id": user_id}, {"notifications": 1}) or {}
    return list(reversed(user.get("notifications", [])))


def mark_user_notification_read(user_id: str, notification_id: str) -> bool:
    result = get_workflow_database().users.update_one(
        {"user_id": user_id, "notifications.notification_id": notification_id},
        {"$set": {"notifications.$.read": True}},
    )
    return result.modified_count > 0


def mark_all_user_notifications_read(user_id: str) -> None:
    get_workflow_database().users.update_one(
        {"user_id": user_id}, {"$set": {"notifications.$[notice].read": True}},
        array_filters=[{"notice.read": False}],
    )


def _bucket() -> GridFSBucket:
    return GridFSBucket(get_workflow_database(), bucket_name="submission_files")


@lru_cache(maxsize=1)
def ensure_workflow_indexes() -> None:
    """Create only the new workflow collections and indexes; never rewrite data."""
    db = get_workflow_database()
    db.users.create_index([("user_id", ASCENDING)], unique=True, name="user_id_unique")
    db.users.create_index([("email", ASCENDING)], unique=True, name="email_unique")
    db.institutions.create_index([("institute_id", ASCENDING)], unique=True, name="institute_id_unique")
    db.institutions.create_index([("name_key", ASCENDING)], unique=True, name="institution_name_unique")
    db.curriculum_submissions.create_index(
        [("institute_id", ASCENDING), ("designer_id", ASCENDING), ("curriculum_id", ASCENDING), ("version", ASCENDING)],
        unique=True,
        name="submission_curriculum_version_unique",
    )
    db.curriculum_submissions.create_index(
        [("status", ASCENDING), ("submitted_at", DESCENDING)],
        name="pending_review_queue",
    )
    db.curriculum_submissions.create_index(
        [("institute_id", ASCENDING), ("designer_id", ASCENDING), ("curriculum_id", ASCENDING)],
        name="institution_curriculum_lookup",
    )
    db.submission_analyses.create_index(
        [("submission_id", ASCENDING), ("created_at", DESCENDING)],
        name="submission_analysis_history",
    )


def _password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    result = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ROUNDS)
    return f"pbkdf2_sha256${_HASH_ROUNDS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(result).decode()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_demo_account(account: Dict[str, Any]) -> Dict[str, Any]:
    """Non-destructively migrate one existing demo identity on first sign-in."""
    ensure_workflow_indexes()
    db = get_workflow_database()
    user_id = str(account["id"])
    email = str(account["email"]).strip().lower()
    existing = db.users.find_one({"$or": [{"user_id": user_id}, {"email": email}]})
    if existing:
        return existing
    record = {
        "user_id": user_id,
        "name": account["name"],
        "email": email,
        "username": email,
        "role": account["role"],
        "institute_id": None,
        "password_hash": _password_hash(account["password"]),
        "status": account.get("status", "Active"),
        "created_at": now_utc(),
        "identity_source": "legacy_demo_migration",
    }
    try:
        db.users.insert_one(record)
    except DuplicateKeyError:
        pass
    return db.users.find_one({"$or": [{"user_id": user_id}, {"email": email}]}) or {}


def migrate_demo_accounts(demo_accounts: List[Dict[str, Any]]) -> None:
    """One-time, non-destructive migration from the legacy in-code registry."""
    ensure_workflow_indexes()
    for account in demo_accounts:
        create_demo_account(account)


def authenticate_demo_user(email: str, password: str, demo_accounts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # Migrate only the account being used. Hashing and inserting every demo
    # account on the first sign-in makes the login request unnecessarily slow.
    ensure_workflow_indexes()
    normalized_email = email.strip().lower()
    legacy = next((item for item in demo_accounts if item["email"].lower() == normalized_email), None)
    if legacy:
        record = create_demo_account(legacy)
    else:
        record = get_workflow_database().users.find_one({"email": normalized_email})
    if not record or record.get("status") != "Active" or not _password_matches(password, record.get("password_hash", "")):
        return None
    return record


def find_user(user_id: str) -> Optional[Dict[str, Any]]:
    ensure_workflow_indexes()
    return get_workflow_database().users.find_one({"user_id": user_id})


def public_user(record: Dict[str, Any]) -> Dict[str, Any]:
    return {key: record.get(key) for key in ("user_id", "name", "email", "username", "role", "institute_id", "status")}


def list_users() -> List[Dict[str, Any]]:
    ensure_workflow_indexes()
    return [public_user(row) for row in get_workflow_database().users.find({}, {"_id": 0, "password_hash": 0}).sort("name", ASCENDING)]


def get_account_profile(user_id: str) -> Dict[str, Any]:
    user = find_user(user_id)
    if not user:
        raise LookupError("Account not found")
    institution = get_workflow_database().institutions.find_one({"institute_id": user.get("institute_id")}) if user.get("institute_id") else None
    return {
        **public_user(user),
        "institute_name": (institution or {}).get("name"),
        "preferences": {"timezone": (user.get("preferences") or {}).get("timezone", "Asia/Kolkata")},
    }


def update_account_preferences(user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"timezone"}
    if not preferences or set(preferences) - allowed:
        raise ValueError("Only time zone, evidence reminders, and decision digest preferences can be changed")
    changes: Dict[str, Any] = {"updated_at": now_utc()}
    if "timezone" in preferences:
        zone = str(preferences["timezone"]).strip()
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid IANA time zone") from exc
        changes["preferences.timezone"] = zone
    db = get_workflow_database()
    record = db.users.find_one_and_update({"user_id": user_id}, {"$set": changes}, return_document=ReturnDocument.AFTER)
    if not record:
        raise LookupError("Account not found")
    return get_account_profile(user_id)


def create_institution(name: str) -> Dict[str, Any]:
    ensure_workflow_indexes()
    clean_name = " ".join(name.split())
    record = {
        "institute_id": str(uuid.uuid4()),
        "name": clean_name,
        "name_key": clean_name.casefold(),
        "status": "Active",
        "created_at": now_utc(),
    }
    get_workflow_database().institutions.insert_one(record)
    return {key: value for key, value in record.items() if key not in {"_id", "name_key"}}


def list_institutions() -> List[Dict[str, Any]]:
    ensure_workflow_indexes()
    return list(get_workflow_database().institutions.find({}, {"_id": 0, "name_key": 0}).sort("name", ASCENDING))


def assign_institution(user_id: str, institute_id: Optional[str]) -> Dict[str, Any]:
    ensure_workflow_indexes()
    db = get_workflow_database()
    user = db.users.find_one({"user_id": user_id})
    if not user:
        raise LookupError("User not found")
    if user.get("role") not in {"designer", "institute"}:
        raise ValueError("Only Designers and Institute Representatives can be linked to an institution")
    if institute_id and not db.institutions.find_one({"institute_id": institute_id, "status": "Active"}):
        raise LookupError("Institution not found")
    db.users.update_one({"_id": user["_id"]}, {"$set": {"institute_id": institute_id, "updated_at": now_utc()}})
    return public_user(db.users.find_one({"_id": user["_id"]}) or {})


def update_user_access(user_id: str, *, role: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    ensure_workflow_indexes()
    if role is not None and role not in ROLES:
        raise ValueError("Unsupported account role")
    if status is not None and status not in {"Active", "Inactive"}:
        raise ValueError("Status must be Active or Inactive")
    changes: Dict[str, Any] = {"updated_at": now_utc()}
    if role is not None:
        changes["role"] = role
        if role not in {"designer", "institute"}:
            changes["institute_id"] = None
    if status is not None:
        changes["status"] = status
    record = get_workflow_database().users.find_one_and_update(
        {"user_id": user_id}, {"$set": changes}, return_document=ReturnDocument.AFTER
    )
    if not record:
        raise LookupError("User not found")
    return public_user(record)


def actor_record(user_id: str, role: str, name: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
    ensure_workflow_indexes()
    db = get_workflow_database()
    record = db.users.find_one({"user_id": user_id})
    if not record:
        # Trusted server middleware identities may be provisioned without a password.
        record = {"user_id": user_id, "email": email or f"{user_id}@identity.invalid", "username": email or user_id, "name": name or user_id, "role": role, "institute_id": None, "status": "Active", "created_at": now_utc(), "identity_source": "trusted_middleware"}
        try:
            db.users.insert_one(record)
        except DuplicateKeyError:
            record = db.users.find_one({"user_id": user_id}) or record
    return record


def store_original_pdf(data: bytes, filename: str, metadata: Dict[str, Any]) -> ObjectId:
    return _bucket().upload_from_stream(filename, data, metadata=metadata)


def read_original_pdf(file_id: ObjectId) -> tuple[bytes, str]:
    stream = _bucket().open_download_stream(file_id)
    return stream.read(), stream.filename


def delete_unsubmitted_draft_pdf(file_id: Any) -> None:
    """Remove a Designer's stored draft PDF after the draft's index is deleted."""
    _bucket().delete(ObjectId(str(file_id)))


def prepared_curricula_for_institute(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not user.get("institute_id"):
        raise PermissionError("Your account is not linked to an institution")
    db = get_workflow_database()
    designer_ids = [row["user_id"] for row in db.users.find({"role": "designer", "institute_id": user["institute_id"], "status": "Active"}, {"user_id": 1})]
    if not designer_ids:
        return []
    rows = db.curricula_metadata.find({"source_type": "submitted_curriculum", "owner_id": {"$in": designer_ids}, "status": "Active", "handoff_status": "Ready for institute"}).sort("uploaded_at", DESCENDING)
    result = []
    for row in rows:
        latest = db.curriculum_submissions.find_one({
            "prepared_document_metadata_id": row["_id"],
        }, sort=[("version", DESCENDING)])
        if latest and latest.get("status") not in {"Revision Required", "Rejected", "Upload Failed"}:
            continue
        result.append({
            "document_id": row.get("document_id"), "curriculum_id": row.get("curriculum_id"),
            "filename": row.get("filename"), "programme": row.get("programme"), "branch": row.get("branch"),
            "year": row.get("year"), "version": row.get("version"), "total_chunks": row.get("total_chunks"),
            "designer_id": row.get("owner_id"), "original_available": bool(row.get("original_file_id")),
            "handoff_status": row.get("handoff_status"),
        })
    return result


def handoff_curriculum(*, designer_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    """Make one of the Designer's prepared PDFs available to their institution."""
    ensure_workflow_indexes()
    return get_workflow_database().curricula_metadata.find_one_and_update(
        {
            "source_type": "submitted_curriculum",
            "owner_id": designer_id,
            "document_id": document_id,
            "status": "Active",
        },
        {"$set": {"handoff_status": "Ready for institute", "handed_off_at": now_utc()}},
        return_document=ReturnDocument.AFTER,
    )


def get_prepared_metadata(user: Dict[str, Any], curriculum_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    if not user.get("institute_id"):
        raise PermissionError("Your account is not linked to an institution")
    db = get_workflow_database()
    designer_ids = [row["user_id"] for row in db.users.find({"role": "designer", "institute_id": user["institute_id"], "status": "Active"}, {"user_id": 1})]
    if not designer_ids:
        return None
    return db.curricula_metadata.find_one({"source_type": "submitted_curriculum", "curriculum_id": curriculum_id, "document_id": document_id, "owner_id": {"$in": designer_ids}, "status": "Active"})


def reserve_submission(*, user: Dict[str, Any], prepared: Dict[str, Any], curriculum_name: str) -> Dict[str, Any]:
    ensure_workflow_indexes()
    db = get_workflow_database()
    latest = db.curriculum_submissions.find_one({
        "institute_id": user["institute_id"],
        "designer_id": prepared["owner_id"],
        "curriculum_id": prepared["curriculum_id"],
    }, sort=[("version", DESCENDING)])
    if latest and latest.get("status") not in {"Revision Required", "Rejected", "Upload Failed"}:
        raise ValueError("This curriculum cannot be submitted again until revision feedback is available")
    version = int(latest["version"]) + 1 if latest else 1
    submission_id = str(uuid.uuid4())
    record = {
        "submission_id": submission_id,
        "curriculum_id": prepared["curriculum_id"],
        "curriculum_name": curriculum_name,
        "designer_id": prepared["owner_id"],
        "institute_representative_id": user["user_id"],
        "institute_id": user["institute_id"],
        "prepared_document_metadata_id": prepared["_id"],
        "prepared_document_id": prepared.get("document_id"),
        "document_id": None,
        "document_filename": None,
        "original_file_id": None,
        "version": version,
        "submitted_at": now_utc(),
        "status": "Uploading",
        "review_history": [],
    }
    db.curriculum_submissions.insert_one(record)
    return serialize_submission(record)


def finalize_submission(submission_id: str, *, document_id: str, filename: str, file_id: ObjectId) -> Dict[str, Any]:
    ensure_workflow_indexes()
    record = get_workflow_database().curriculum_submissions.find_one_and_update(
        {"submission_id": submission_id, "status": "Uploading"},
        {"$set": {"document_id": document_id, "document_filename": filename, "original_file_id": file_id, "status": "Pending", "submitted_at": now_utc()}},
        return_document=ReturnDocument.AFTER,
    )
    if not record:
        raise RuntimeError("Submission upload could not be finalized")
    if record.get("version", 1) > 1:
        from backend.services.change_request_service import set_resubmission_request_status
        set_resubmission_request_status(record, "Resubmitted")
    for reviewer in get_workflow_database().users.find({"role": "reviewer", "status": "Active"}, {"user_id": 1}):
        notify_user(reviewer["user_id"], "Curriculum ready for review", f"{record.get('curriculum_name') or record['curriculum_id']} v{record['version']} is in the shared Reviewer Queue.", submission_id)
    return serialize_submission(record)


def fail_submission_upload(submission_id: str) -> None:
    ensure_workflow_indexes()
    get_workflow_database().curriculum_submissions.update_one(
        {"submission_id": submission_id, "status": "Uploading"},
        {"$set": {"status": "Upload Failed", "upload_failed_at": now_utc()}},
    )


def serialize_submission(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "submission_id": record["submission_id"], "curriculum_id": record["curriculum_id"],
        "curriculum_name": record.get("curriculum_name") or record["curriculum_id"],
        "designer_id": record["designer_id"], "institute_representative_id": record["institute_representative_id"],
        "institute_id": record["institute_id"], "document_id": record["document_id"],
        "prepared_document_id": record.get("prepared_document_id"),
        "document_filename": record["document_filename"], "version": record["version"],
        "submitted_at": record["submitted_at"], "status": record["status"],
        "published_at": record.get("published_at"), "published_by": record.get("published_by"),
        "institution_feedback": record.get("institution_feedback", []),
        "review_history": record.get("review_history", []),
    }


def list_pending_submissions() -> List[Dict[str, Any]]:
    ensure_workflow_indexes()
    db = get_workflow_database()
    results = []
    for row in db.curriculum_submissions.find({"status": "Pending"}).sort("submitted_at", ASCENDING):
        institute = db.institutions.find_one({"institute_id": row["institute_id"]}) or {}
        results.append({**serialize_submission(row), "institute_name": institute.get("name", "Institution"), "review_action": True})
    return results


def list_publication_eligible(institute_id: str) -> List[Dict[str, Any]]:
    db = get_workflow_database()
    return [serialize_submission(row) for row in db.curriculum_submissions.find(
        {"institute_id": institute_id, "status": "Accepted"}
    ).sort("submitted_at", DESCENDING)]


def list_published_curricula(institute_id: str) -> List[Dict[str, Any]]:
    db = get_workflow_database()
    return [serialize_submission(row) for row in db.curriculum_submissions.find(
        {"institute_id": institute_id, "status": "Published"}
    ).sort("published_at", DESCENDING)]


def list_audit_events(limit: int = 300) -> List[Dict[str, Any]]:
    """Build an admin activity view from existing immutable submission history."""
    db = get_workflow_database()
    events: List[Dict[str, Any]] = []
    rows = db.curriculum_submissions.find(
        {"status": {"$ne": "Uploading"}},
        {
            "_id": 0, "submission_id": 1, "curriculum_id": 1, "curriculum_name": 1,
            "version": 1, "institute_id": 1, "institute_representative_id": 1,
            "submitted_at": 1, "review_history": 1, "workflow_history": 1,
        },
    ).sort("submitted_at", DESCENDING).limit(max(1, min(int(limit), 1000)))
    for row in rows:
        institute = db.institutions.find_one({"institute_id": row.get("institute_id")}) or {}
        common = {
            "submission_id": row.get("submission_id"),
            "curriculum_id": row.get("curriculum_id"),
            "curriculum_name": row.get("curriculum_name") or row.get("curriculum_id"),
            "version": row.get("version"),
            "institute_id": row.get("institute_id"),
            "institute_name": institute.get("name", "Institution"),
        }
        events.append({
            **common, "event_id": f"{row.get('submission_id')}:submitted",
            "action": "Submission created", "actor_id": row.get("institute_representative_id"),
            "created_at": row.get("submitted_at"), "details": "Official curriculum PDF submitted for review.",
        })
        for review in row.get("review_history", []):
            decision = review.get("status") or review.get("decision") or "Review decision"
            events.append({
                **common, "event_id": f"{row.get('submission_id')}:{review.get('review_id')}",
                "action": decision, "actor_id": review.get("reviewer_id"),
                "created_at": review.get("decided_at"),
                "details": review.get("feedback") or review.get("decision_justification") or "",
                "decision_justification": review.get("decision_justification", ""),
            })
        for item in row.get("workflow_history", []):
            events.append({
                **common, "event_id": f"{row.get('submission_id')}:{item.get('event')}:{item.get('created_at')}",
                "action": item.get("event", "Workflow updated"), "actor_id": item.get("actor_id"),
                "created_at": item.get("created_at"), "details": item.get("details", ""),
            })
    actor_ids = {event.get("actor_id") for event in events if event.get("actor_id")}
    names = {user["user_id"]: user.get("name", user["user_id"]) for user in db.users.find(
        {"user_id": {"$in": list(actor_ids)}}, {"user_id": 1, "name": 1}
    )}
    for event in events:
        event["actor_name"] = names.get(event.get("actor_id"), "Unknown user")
    def event_timestamp(event: Dict[str, Any]) -> float:
        value = event.get("created_at")
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return 0.0
        if not isinstance(value, datetime):
            return 0.0
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    events.sort(key=event_timestamp, reverse=True)
    return events[:max(1, min(int(limit), 1000))]


def publish_submission(*, submission_id: str, institute_id: str, publisher_id: str) -> Dict[str, Any]:
    ensure_workflow_indexes()
    now = now_utc()
    record = get_workflow_database().curriculum_submissions.find_one_and_update(
        {"submission_id": submission_id, "institute_id": institute_id, "status": "Accepted"},
        {"$set": {"status": "Published", "published_at": now, "published_by": publisher_id},
         "$push": {"workflow_history": {"event": "Published", "actor_id": publisher_id, "created_at": now}}},
        return_document=ReturnDocument.AFTER,
    )
    if not record:
        raise RuntimeError("Only an accepted submission for your institution can be published")
    notify_user(record["designer_id"], "Curriculum published", f"{record.get('curriculum_name') or record['curriculum_id']} v{record['version']} was published by your institution.", submission_id)
    return serialize_submission(record)


def record_institute_feedback(*, submission_id: str, institute_id: str, author_id: str, kind: str,
                              category: str, observation: str, suggested_change: str = "",
                              priority: str = "Medium") -> Dict[str, Any]:
    if kind not in {"feedback", "change_request"}:
        raise ValueError("Feedback type is invalid")
    if not observation.strip():
        raise ValueError("Describe the delivery feedback")
    if kind == "change_request" and not suggested_change.strip():
        raise ValueError("Describe the suggested curriculum change")
    if priority not in {"High", "Medium", "Low"}:
        raise ValueError("Priority is invalid")
    db = get_workflow_database()
    published = db.curriculum_submissions.find_one(
        {"submission_id": submission_id, "institute_id": institute_id, "status": "Published"}
    )
    if not published:
        raise LookupError("Published curriculum not found for your institution")
    submission = db.curriculum_submissions.find_one_and_update(
        {"submission_id": submission_id, "institute_id": institute_id, "status": "Published"},
        {"$push": {"institution_feedback": {
            "feedback_id": str(uuid.uuid4()), "kind": kind, "category": category.strip()[:80],
            "curriculum_id": published["curriculum_id"], "submission_id": submission_id,
            "curriculum_version": published["version"], "institute_id": institute_id,
            "observation": observation.strip()[:3000], "suggested_change": suggested_change.strip()[:2000],
            "priority": priority, "author_id": author_id, "created_at": now_utc(),
            "status": "Pending Designer Action" if kind == "change_request" else "Recorded",
            "designer_response": "", "resubmission_submission_id": None,
        }}},
        return_document=ReturnDocument.AFTER,
    )
    if not submission:
        raise LookupError("Published curriculum not found for your institution")
    entry = submission["institution_feedback"][-1]
    if kind == "change_request":
        notify_user(submission["designer_id"], "Institution requested a curriculum change", f"{submission.get('curriculum_name') or submission['curriculum_id']} v{submission['version']} has a new change request.", submission_id)
    return entry


def find_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    ensure_workflow_indexes()
    return get_workflow_database().curriculum_submissions.find_one({"submission_id": submission_id})


def authorize_submission_access(user: Dict[str, Any], submission: Dict[str, Any]) -> bool:
    if user.get("role") == "reviewer":
        return submission.get("status") in {"Pending", "Accepted", "Revision Required", "Rejected", "Published"}
    if user.get("role") == "designer":
        return user.get("user_id") == submission.get("designer_id") and user.get("institute_id") == submission.get("institute_id")
    if user.get("role") == "institute":
        return bool(user.get("institute_id")) and user.get("institute_id") == submission.get("institute_id")
    return False


def record_analysis(submission: Dict[str, Any], reviewer_id: str, report: Dict[str, Any]) -> None:
    ensure_workflow_indexes()
    db = get_workflow_database()
    current_checks = {}
    for criterion in report.get("criteria", []):
        for check in criterion.get("checks", []):
            current_checks[check.get("check_id")] = check
    active = {
        check_id: check for check_id, check in current_checks.items()
        if check.get("status") in {"fail", "partial"}
    }
    prior_submissions = list(db.curriculum_submissions.find({
        "designer_id": submission["designer_id"],
        "curriculum_id": submission["curriculum_id"],
        "version": {"$lt": submission["version"]},
    }, {"submission_id": 1, "version": 1}))
    prior_ids = [row["submission_id"] for row in prior_submissions]
    prior_by_version = {}
    if prior_ids:
        for prior_analysis in db.submission_analyses.find({"submission_id": {"$in": prior_ids}}).sort("created_at", DESCENDING):
            version = int(prior_analysis.get("version", 0))
            prior_by_version.setdefault(version, prior_analysis)
    previous = next(iter(prior_by_version.values()), {})
    previous_findings = {row.get("finding_id"): row for row in previous.get("finding_snapshot", [])}
    prior_open = {key: value for key, value in previous_findings.items() if value.get("status") != "Resolved"}
    prior_resolved = {key: value for key, value in previous_findings.items() if value.get("status") == "Resolved"}
    snapshot = []
    for check_id, check in active.items():
        if check_id in prior_open:
            state = "Open"
            first_version = prior_open[check_id].get("first_detected_version", submission["version"])
        elif check_id in prior_resolved:
            state = "Reopened"
            first_version = prior_resolved[check_id].get("first_detected_version", submission["version"])
        else:
            state = "Newly Detected"
            first_version = submission["version"]
        snapshot.append({
            "finding_id": check_id, "original_issue": check.get("title", check_id),
            "severity": "High" if check.get("status") == "fail" else "Medium",
            "status": state, "first_detected_version": first_version,
            "version": submission["version"], "resolution_evidence": [],
            "curriculum_evidence": check.get("curriculum_evidence", []),
            "related_check_ids": [check_id],
        })
    for check_id, old in prior_open.items():
        if check_id not in active:
            latest_check = current_checks.get(check_id, {})
            if latest_check.get("status") == "pass":
                snapshot.append({
                    **old, "finding_id": check_id, "status": "Resolved",
                    "resolved_in_version": submission["version"],
                    "version": submission["version"],
                    "resolution_evidence": latest_check.get("curriculum_evidence", []),
                })
            else:
                # Missing or unevaluable evidence cannot prove that a prior issue
                # was corrected. Keep it outstanding until a check passes.
                snapshot.append({
                    **old, "finding_id": check_id, "status": "Open",
                    "version": submission["version"], "resolution_evidence": [],
                    "curriculum_evidence": latest_check.get("curriculum_evidence", old.get("curriculum_evidence", [])),
                })
    db.submission_analyses.insert_one({
        "analysis_id": str(uuid.uuid4()), "submission_id": submission["submission_id"],
        "version": submission["version"], "document_id": submission["document_id"],
        "reviewer_id": reviewer_id, "created_at": now_utc(), "report": report,
        "finding_snapshot": snapshot,
    })


def analysis_history(submission_id: str) -> List[Dict[str, Any]]:
    ensure_workflow_indexes()
    rows = get_workflow_database().submission_analyses.find({"submission_id": submission_id}, {"_id": 0}).sort("created_at", DESCENDING)
    return list(rows)


def improvement_history(designer_id: str) -> List[Dict[str, Any]]:
    """Build version trends only from stored submissions and analyzer runs."""
    db = get_workflow_database()
    submissions = list(db.curriculum_submissions.find(
        {"designer_id": designer_id, "status": {"$in": ["Pending", "Accepted", "Revision Required", "Rejected"]}},
    ).sort([("curriculum_id", ASCENDING), ("version", ASCENDING)]))
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for submission in submissions:
        grouped.setdefault(submission["curriculum_id"], []).append(submission)
    output = []
    for curriculum_id, versions in grouped.items():
        version_rows = []
        for submission in versions:
            analysis = db.submission_analyses.find_one(
                {"submission_id": submission["submission_id"]}, sort=[("created_at", DESCENDING)]
            )
            if not analysis:
                continue
            report = analysis.get("report", {})
            snapshot = analysis.get("finding_snapshot")
            if snapshot is None:
                snapshot = []
                for criterion in report.get("criteria", []):
                    for check in criterion.get("checks", []):
                        if check.get("status") in {"fail", "partial"}:
                            snapshot.append({
                                "finding_id": check.get("check_id"), "original_issue": check.get("title"),
                                "severity": "High" if check.get("status") == "fail" else "Medium",
                                "status": "Open", "first_detected_version": submission["version"],
                                "version": submission["version"], "resolution_evidence": [],
                                "curriculum_evidence": check.get("curriculum_evidence", []),
                            })
            version_rows.append({
                "submission_id": submission["submission_id"],
                "version": submission["version"], "status": submission["status"],
                "analyzed_at": analysis.get("created_at"), "score": report.get("overall_score"),
                "coverage": report.get("overall_evaluation_coverage"),
                "finding_snapshot": snapshot,
                "review_history": submission.get("review_history", []),
            })
        if version_rows:
            latest = version_rows[-1]
            open_statuses = {"Open", "Reopened", "Newly Detected", "In Progress"}
            latest_findings = [row for row in latest["finding_snapshot"] if row.get("status") in open_statuses]
            output.append({
                "curriculum_id": curriculum_id,
                "curriculum_name": versions[-1].get("curriculum_name") or curriculum_id,
                "versions": version_rows,
                "latest_score": latest.get("score"),
                "previous_score": version_rows[-2].get("score") if len(version_rows) > 1 else None,
                "total_improvement": latest.get("score") - version_rows[0].get("score") if latest.get("score") is not None and version_rows[0].get("score") is not None else None,
                "latest_findings": latest_findings,
                "resolved_findings": [row for row in latest["finding_snapshot"] if row.get("status") == "Resolved"],
                "new_findings": [row for row in latest["finding_snapshot"] if row.get("status") == "Newly Detected"],
                "reopened_findings": [row for row in latest["finding_snapshot"] if row.get("status") == "Reopened"],
            })
    return output


def decide_submission(*, submission_id: str, reviewer_id: str, decision: str, feedback: str, justification: str = "", recommendation: Optional[str] = None) -> Dict[str, Any]:
    ensure_workflow_indexes()
    status_map = {"accept": "Accepted", "review": "Revision Required", "reject": "Rejected"}
    if decision not in status_map:
        raise ValueError("Decision must be accept, review, or reject")
    if decision in {"review", "reject"} and not feedback.strip():
        raise ValueError("Feedback is required for revision and rejection decisions")
    db = get_workflow_database()
    submission = db.curriculum_submissions.find_one({"submission_id": submission_id})
    if not submission:
        raise RuntimeError("Submission not found")
    if decision == "accept" and not db.submission_analyses.find_one({"submission_id": submission_id}):
        raise ValueError("Run the Reviewer Analyzer before accepting this submission")
    review = {
        "review_id": str(uuid.uuid4()), "reviewer_id": reviewer_id, "decision": decision,
        "status": status_map[decision], "feedback": feedback.strip(),
        "decision_justification": justification.strip(), "analyzer_recommendation": recommendation,
        "decided_at": now_utc(),
    }
    if decision in {"review", "reject"}:
        from backend.services.change_request_service import change_requests_for_decision
        review["change_requests"] = change_requests_for_decision(submission, reviewer_id, decision, feedback.strip())
    updated = db.curriculum_submissions.find_one_and_update(
        {"submission_id": submission_id, "status": "Pending"},
        {"$set": {"status": status_map[decision]}, "$push": {"review_history": review}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise RuntimeError("Submission is no longer pending review")
    if decision == "accept":
        from backend.services.change_request_service import update_requests_linked_to_submission
        update_requests_linked_to_submission(submission_id, "Resolved")
    notice = {"accept": "accepted", "review": "returned for revision", "reject": "rejected"}[decision]
    notify_user(submission["designer_id"], "Reviewer decision recorded", f"{submission.get('curriculum_name') or submission['curriculum_id']} v{submission['version']} was {notice}.", submission_id)
    if submission.get("institute_representative_id"):
        notify_user(submission["institute_representative_id"], "Reviewer decision recorded", f"{submission.get('curriculum_name') or submission['curriculum_id']} v{submission['version']} was {notice}.", submission_id)
    return serialize_submission(updated)


def create_institute_user(*, name: str, email: str, role: str, password: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Explicit account provisioning; institution assignment is a separate admin action."""
    ensure_workflow_indexes()
    if role not in ROLES or len(password) < 8 or not name.strip() or "@" not in email:
        raise ValueError("Name, valid email, supported role and an 8-character password are required")
    record = {"user_id": user_id or str(uuid.uuid4()), "name": name.strip(), "email": email.strip().lower(), "username": email.strip().lower(), "role": role, "institute_id": None, "password_hash": _password_hash(password), "status": "Active", "created_at": now_utc(), "identity_source": "admin_provisioned"}
    get_workflow_database().users.insert_one(record)
    return public_user(record)


