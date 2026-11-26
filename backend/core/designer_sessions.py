"""Verified Designer accounts and opaque browser sessions in the Designer database."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
from pymongo import ReturnDocument

from backend.data.database import get_designer_database

COOKIE = "aicte_designer_session"
SESSION_SECONDS = 8 * 60 * 60
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_LOCAL_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def enabled():
    return os.getenv("ENABLE_VERIFIED_DESIGNER_AUTH", "").strip().lower() in {"true", "1", "yes"}


def local_video_enabled():
    return os.getenv("ENABLE_LOCAL_DESIGNER_VIDEO_LOGIN", "").strip().lower() in {"true", "1", "yes"}


def _local_request(request: Request):
    return (
        request.client is not None and request.client.host in _LOCAL_HOSTS
        and request.url.hostname in _LOCAL_HOSTS
        and not any(request.headers.get(key) for key in ("cf-connecting-ip", "x-forwarded-host"))
    )


def password_digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024).hex()


def _sessions():
    return get_designer_database()["verified_designer_sessions"]


def accounts():
    return get_designer_database()["verified_designer_accounts"]


def _token_id(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _limit_attempts(email, request):
    # Both buckets use atomic counters, including across multiple workers.
    now = datetime.now(timezone.utc)
    window = int(now.timestamp()) // 600
    address = request.client.host if request.client else "unknown"
    for scope, limit in ((f"client:{address}", 60), (f"account:{email}", 10)):
        key = _token_id(f"{window}:{scope}")
        row = get_designer_database()["verified_designer_login_attempts"].find_one_and_update(
            {"_id": key},
            {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(minutes=20)}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        if row["count"] > limit:
            raise HTTPException(429, "Too many sign-in attempts. Try again in ten minutes.")


def verified_login(email, password, request: Request, response: Response):
    if not enabled():
        return None
    _limit_attempts(email, request)
    account = accounts().find_one({"_id": email})
    if account is None:
        # Use the same password work factor when there is no account.
        password_digest(password, "0" * 32)
        return None
    actual = password_digest(password, account["salt"])
    if not hmac.compare_digest(actual, account["password_digest"]) or account.get("active") is not True:
        raise HTTPException(401, "Invalid email or password")
    _issue_session(request, response, {"account": email, "revision": account["revision"]})
    return {
        "id": account["owner_id"], "name": account["name"], "email": email,
        "role": "designer", "organization": account["organization"], "verified": True,
    }


def _issue_session(request, response, identity):
    revoke(request, response)
    token = secrets.token_urlsafe(32)
    _sessions().insert_one({
        "_id": _token_id(token), **identity,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS),
    })
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


def start_local_designer_session(user, request: Request, response: Response):
    if (
        not local_video_enabled() or user["role"] != "designer" or user["status"] != "Active"
        or not _local_request(request) or request.headers.get("origin") not in _LOCAL_ORIGINS
    ):
        return False
    _issue_session(request, response, {"local_owner_id": user["id"]})
    return True


def session_identity(request: Request):
    token = request.cookies.get(COOKIE, "")
    local = local_video_enabled() and _local_request(request)
    if not (enabled() or local) or not _TOKEN.fullmatch(token):
        return None
    session = _sessions().find_one({
        "_id": _token_id(token), "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not session:
        return None
    if "local_owner_id" in session:
        return {"id": session["local_owner_id"], "role": "designer"} if local else None
    if not enabled():
        return None
    account = accounts().find_one({
        "_id": session["account"], "revision": session["revision"], "active": True,
    }, {"owner_id": 1})
    return {"id": account["owner_id"], "role": "designer"} if account else None


def revoke(request: Request, response: Response):
    token = request.cookies.get(COOKIE, "")
    if (enabled() or (local_video_enabled() and _local_request(request))) and _TOKEN.fullmatch(token):
        _sessions().delete_one({"_id": _token_id(token)})
    response.delete_cookie(COOKIE, httponly=True, secure=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
