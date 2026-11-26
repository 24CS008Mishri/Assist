"""Text transcript history for the owner of a virtual consultation."""
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.auth import AuthenticatedUser, require_verified_designer
from backend.data.database import get_designer_database

router = APIRouter(prefix="/transcripts")
PRIVATE_RESPONSE = {"Cache-Control": "no-store"}
PAGE_SIZE = 30


def _history():
    return get_designer_database()["live_curriculum_transcripts"]


def _turns():
    return get_designer_database()["live_curriculum_transcript_turns"]


@lru_cache(maxsize=1)
def _ensure_indexes():
    _history().create_index([("owner_id", 1), ("has_turns", 1), ("created_at", -1), ("_id", -1)])
    _turns().create_index([("transcript_id", 1), ("sequence", 1)])


def _owned_history(owner_id, history_id, projection=None):
    document = _history().find_one({"_id": history_id, "owner_id": owner_id}, projection)
    if document is None:
        raise HTTPException(404, "Transcript not found.")
    return document


def continue_transcript(owner_id: str, history_id: UUID, document_id: str | None, curriculum_id: str | None):
    history = _owned_history(owner_id, str(history_id), {"document_id": 1, "curriculum_id": 1})
    if (history["document_id"], history["curriculum_id"]) != (document_id, curriculum_id):
        raise HTTPException(409, "The curriculum has changed. Start a new consultation to continue.")
    return str(history_id)


def new_transcript(owner_id: str, document_id: str | None, curriculum_id: str | None, title: str, language: str):
    _ensure_indexes()
    history_id = str(uuid4())
    _history().insert_one({
        "_id": history_id,
        "owner_id": owner_id,
        "document_id": document_id,
        "curriculum_id": curriculum_id,
        "title": title,
        "language": language,
        "created_at": datetime.now(timezone.utc),
        "has_turns": False,
    })
    return history_id


class TranscriptTurn(BaseModel):
    id: UUID
    sequence: int = Field(ge=1)
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=12000)


@router.post("/{history_id}/turns", status_code=204)
def save_turn(history_id: UUID, body: TranscriptTurn, user: AuthenticatedUser = Depends(require_verified_designer)):
    transcript_id = str(history_id)
    _owned_history(user.user_id, transcript_id, {"_id": 1})
    _turns().update_one(
        {"_id": f"{transcript_id}:{body.id}"},
        {"$setOnInsert": {
            "transcript_id": transcript_id, "sequence": body.sequence, "role": body.role, "text": body.text,
        }},
        upsert=True,
    )
    _history().update_one(
        {"_id": transcript_id, "owner_id": user.user_id, "has_turns": False},
        {"$set": {"has_turns": True}},
    )
    return Response(status_code=204, headers=PRIVATE_RESPONSE)


@router.get("")
def list_transcripts(
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(require_verified_designer),
):
    rows = list(_history().find(
        {"owner_id": user.user_id, "has_turns": True},
        {"title": 1, "language": 1, "created_at": 1},
    ).sort([("created_at", -1), ("_id", -1)]).skip(offset).limit(PAGE_SIZE + 1))
    return JSONResponse({
        "items": [_summary(row) for row in rows[:PAGE_SIZE]],
        "next_offset": offset + PAGE_SIZE if len(rows) > PAGE_SIZE else None,
    }, headers=PRIVATE_RESPONSE)


def _summary(row):
    return {
        "id": row["_id"], "title": row["title"], "language": row["language"],
        "created_at": row["created_at"].replace(tzinfo=timezone.utc).isoformat(),
    }


@router.get("/{history_id}")
def read_transcript(history_id: UUID, user: AuthenticatedUser = Depends(require_verified_designer)):
    transcript_id = str(history_id)
    row = _owned_history(user.user_id, transcript_id, {"title": 1, "language": 1, "created_at": 1})
    turns = list(_turns().find(
        {"transcript_id": transcript_id}, {"role": 1, "text": 1},
    ).sort([("sequence", 1), ("_id", 1)]))
    return JSONResponse({**_summary(row), "turns": turns}, headers=PRIVATE_RESPONSE)
