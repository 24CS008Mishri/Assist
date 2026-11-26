"""Tavus conversation lifecycle and authenticated evidence callbacks."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import os
import re
from functools import lru_cache
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from starlette.concurrency import run_in_threadpool
from typing import Literal

from backend.core.auth import AuthenticatedUser, require_verified_designer
from backend.data.database import get_designer_database, get_designer_metadata_collection
from backend.services.live_curriculum_knowledge import PRIVATE_SOURCE, answer_live_question

router = APIRouter(prefix="/api/live-assistant", tags=["live-assistant"])
logger = logging.getLogger(__name__)
LANGUAGES = ("en-in", "hi", "gu")
MAX_CALL_SECONDS = 600
TAVUS_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")


class StartRequest(BaseModel):
    document_id: str | None = Field(default=None, max_length=150)
    curriculum_id: str | None = Field(default=None, max_length=250)
    language: Literal["en-in", "hi", "gu"] = "en-in"


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Literal["answer_curriculum_question"]
    conversation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    tool_call_id: str = Field(min_length=1, max_length=150)
    arguments: str = Field(max_length=8000)


class ToolArguments(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    search_query: str = Field(min_length=1, max_length=1200)
    language: Literal["en-in", "hi", "gu", "mixed"]


def _configuration():
    key = os.getenv("TAVUS_API_KEY", "").strip()
    pal_id = os.getenv("TAVUS_PAL_ID", "").strip()
    secret = os.getenv("TAVUS_TOOL_SECRET", "").strip()
    if not key or not TAVUS_ID.fullmatch(pal_id) or len(secret) < 32:
        raise HTTPException(503, "Live consultations need a configured Tavus PAL and signing secret.")
    return key, pal_id, secret


def _sessions():
    collection = get_designer_database()["live_curriculum_sessions"]
    _ensure_session_indexes()
    return collection


@lru_cache(maxsize=1)
def _ensure_session_indexes():
    collection = get_designer_database()["live_curriculum_sessions"]
    collection.create_index("expires_at", expireAfterSeconds=0)
    collection.create_index("conversation_id", unique=True, sparse=True)


def _tavus_post(key, suffix="", body=None):
    try:
        result = httpx.post(
            f"https://tavusapi.com/v2/conversations{suffix}",
            headers={"x-api-key": key}, json=body, timeout=15,
        )
        if suffix and result.status_code == 404:
            return {}
        if result.status_code == 429:
            raise HTTPException(503, "Tavus is at its current limit. Try again shortly.")
        result.raise_for_status()
        return result.json() if result.content and not suffix else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Could not communicate with Tavus. Check the PAL configuration or retry.") from exc


def _embed_url(payload):
    location = urlsplit(payload.get("conversation_url", ""))
    token = payload.get("meeting_token")
    if (
        location.scheme != "https" or not location.hostname
        or not location.hostname.endswith(".daily.co")
        or location.username or location.password or not isinstance(token, str) or not token
    ):
        raise HTTPException(502, "Tavus did not return a private video room.")
    return urlunsplit((location.scheme, location.netloc, location.path, urlencode({"t": token}), ""))


@router.post("/sessions")
def start_session(body: StartRequest, user: AuthenticatedUser = Depends(require_verified_designer)):
    key, pal_id, _ = _configuration()
    if bool(body.document_id) != bool(body.curriculum_id):
        raise HTTPException(422, "Select a curriculum and its document version together.")
    if body.document_id and not get_designer_metadata_collection().find_one(
        {"owner_id": user.user_id, "source_type": PRIVATE_SOURCE,
         "document_id": body.document_id, "curriculum_id": body.curriculum_id,
         "status": "Active"}, {"_id": 1}
    ):
        raise HTTPException(404, "Curriculum not found.")

    sessions = _sessions()
    now = datetime.now(timezone.utc)
    reservation = uuid4().hex
    try:
        sessions.find_one_and_update(
            {"_id": user.user_id, "$or": [{"expires_at": {"$lte": now}}, {"expires_at": {"$exists": False}}]},
            {"$set": {"reservation": reservation, "expires_at": now + timedelta(seconds=40)},
             "$unset": {"conversation_id": "", "document_id": "", "curriculum_id": "",
                        "sources": "", "state": ""}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(409, "A consultation is already running. End it before starting another.")

    conversation_id = None
    try:
        payload = _tavus_post(key, body={
            "pal_id": pal_id,
            "require_auth": True,
            "max_participants": 2,
            "custom_greeting": {
                "en-in": "Hello, I'm the AICTE Assist curriculum assistant. How can I help?",
                "hi": "नमस्ते, मैं AICTE Assist की पाठ्यक्रम सहायक हूँ। मैं आपकी कैसे मदद कर सकती हूँ?",
                "gu": "નમસ્તે, હું AICTE Assist ની અભ્યાસક્રમ સહાયક છું. હું તમને કેવી રીતે મદદ કરી શકું?",
            }[body.language],
            "properties": {
                "languages": [body.language, *(lang for lang in LANGUAGES if lang != body.language)],
                "max_call_duration": MAX_CALL_SECONDS,
                "participant_absent_timeout": 60,
                "participant_left_timeout": 0,
            },
        })
        provider_id = payload.get("conversation_id", "")
        if not isinstance(provider_id, str) or not TAVUS_ID.fullmatch(provider_id):
            raise HTTPException(502, "Tavus did not return a valid consultation ID.")
        conversation_id = provider_id
        embed_url = _embed_url(payload)
        expires = datetime.now(timezone.utc) + timedelta(seconds=MAX_CALL_SECONDS)
        updated = sessions.update_one(
            {"_id": user.user_id, "reservation": reservation},
            {"$set": {"conversation_id": conversation_id, "document_id": body.document_id,
                      "curriculum_id": body.curriculum_id,
                      "expires_at": expires, "sources": [], "state": "active"}},
        )
        if not updated.matched_count:
            raise HTTPException(409, "The session expired during setup. Please retry.")
        return JSONResponse(
            {"id": conversation_id, "embed_url": embed_url, "expires_at": expires.isoformat()},
            headers={"Cache-Control": "no-store"},
        )
    except Exception:
        try:
            if conversation_id:
                _tavus_post(key, f"/{conversation_id}/end")
        finally:
            sessions.delete_one({"_id": user.user_id, "reservation": reservation})
        raise


@router.get("/sessions/current")
def current_session(user: AuthenticatedUser = Depends(require_verified_designer)):
    session = _sessions().find_one(
        {"_id": user.user_id, "expires_at": {"$gt": datetime.now(timezone.utc)},
         "state": {"$in": ["active", "ending"]}},
        {"conversation_id": 1},
    )
    return JSONResponse({"id": session["conversation_id"] if session else None},
                        headers={"Cache-Control": "no-store"})


@router.get("/sessions/{conversation_id}/sources")
def session_sources(conversation_id: str, user: AuthenticatedUser = Depends(require_verified_designer)):
    row = _sessions().find_one(
        {"_id": user.user_id, "conversation_id": conversation_id, "state": "active",
         "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"sources": 1},
    )
    if row is None:
        raise HTTPException(404, "Consultation expired or unavailable.")
    return JSONResponse({"sources": row.get("sources", [])}, headers={"Cache-Control": "no-store"})


@router.delete("/sessions/{conversation_id}", status_code=204)
def end_session(conversation_id: str, user: AuthenticatedUser = Depends(require_verified_designer)):
    key, _, _ = _configuration()
    scope = {"_id": user.user_id, "conversation_id": conversation_id}
    if not TAVUS_ID.fullmatch(conversation_id):
        return Response(status_code=204)
    sessions = _sessions()
    if sessions.update_one(scope, {"$set": {"state": "ending", "sources": []}}).matched_count:
        _tavus_post(key, f"/{conversation_id}/end")
        sessions.delete_one(scope)
    return Response(status_code=204)


def close_designer_consultation(owner_id: str):
    try:
        row = _sessions().find_one_and_update(
            {"_id": owner_id, "state": "active", "expires_at": {"$gt": datetime.now(timezone.utc)}},
            {"$set": {"state": "ending", "sources": []}},
        )
        if row:
            end_session(row["conversation_id"], AuthenticatedUser(owner_id, "designer"))
    except (HTTPException, RuntimeError, PyMongoError):
        logger.warning("Could not close the Designer's live room during sign-out")


def _answer_tool(event: ToolRequest, arguments: ToolArguments):
    scope = {"conversation_id": event.conversation_id, "state": "active",
             "expires_at": {"$gt": datetime.now(timezone.utc)}}
    sessions = _sessions()
    row = sessions.find_one(scope)
    if row is None:
        raise HTTPException(404, "Consultation expired or unavailable.")
    answer, sources = answer_live_question(
        row["_id"], row.get("document_id"), arguments.question,
        arguments.search_query, arguments.language, curriculum_id=row.get("curriculum_id"),
    )
    updated = sessions.update_one(
        {**scope, "_id": row["_id"], "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"$set": {"sources": sources}},
    )
    if not updated.matched_count:
        raise HTTPException(404, "Consultation expired or unavailable.")
    return answer


@router.post("/tavus-tool", response_class=PlainTextResponse)
async def tavus_tool(request: Request):
    _, _, secret = _configuration()
    signature = request.headers.get("x-tavus-signature", "")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", signature):
        raise HTTPException(401, "Invalid tool signature.")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 24000:
            raise HTTPException(413, "Tool request is too large.")
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise HTTPException(401, "Invalid tool signature.")
    try:
        event = ToolRequest.model_validate_json(raw)
        arguments = ToolArguments.model_validate_json(event.arguments)
        answer = await run_in_threadpool(_answer_tool, event, arguments)
        return PlainTextResponse(answer, headers={"Cache-Control": "no-store"})
    except ValidationError as exc:
        raise HTTPException(422, "Invalid curriculum tool arguments.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Curriculum evidence tool failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Curriculum evidence is temporarily unavailable.") from exc
