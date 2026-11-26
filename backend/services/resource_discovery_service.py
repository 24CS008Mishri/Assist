"""Live discovery adapters for public academic and educational catalogs."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.data.database import get_designer_metadata_collection, get_workflow_database


TIMEOUT_SECONDS = 8


def _get_json(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "AICTE-Assist/1.0"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean(value: str, limit: int = 520) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _google_books(subject: str) -> List[Dict[str, Any]]:
    params = {"q": subject, "maxResults": 8, "printType": "books", "orderBy": "relevance"}
    key = os.getenv("GOOGLE_BOOKS_API_KEY", "").strip()
    if key:
        params["key"] = key
    data = _get_json("https://www.googleapis.com/books/v1/volumes?" + urlencode(params))
    rows = []
    for item in data.get("items", []):
        info = item.get("volumeInfo") or {}
        access = item.get("accessInfo") or {}
        url = info.get("previewLink") or info.get("infoLink") or item.get("selfLink")
        if not info.get("title") or not url:
            continue
        rows.append({
            "resource_id": f"google-books:{item.get('id', url)}",
            "title": info["title"], "resource_type": "Book",
            "author": ", ".join(info.get("authors", [])) or info.get("publisher", "Author not listed"),
            "publisher": info.get("publisher"), "description": _clean(info.get("description", "")),
            "topics": info.get("categories", []), "publication_year": str(info.get("publishedDate", ""))[:4] or None,
            "source": "Google Books", "url": url,
            "availability": "Preview available" if info.get("previewLink") else "Bibliographic details",
        })
    return rows


def _openalex_abstract(index: Dict[str, List[int]]) -> str:
    words = [""] * (max((max(positions) for positions in index.values() if positions), default=-1) + 1)
    for word, positions in index.items():
        for position in positions:
            if 0 <= position < len(words):
                words[position] = word
    return " ".join(words)[:520]


def _openalex_works(subject: str) -> List[Dict[str, Any]]:
    params = {"search": subject, "per-page": 10,
              "select": "id,doi,display_name,publication_year,authorships,abstract_inverted_index,primary_location,open_access,type,topics"}
    email = os.getenv("OPENALEX_MAILTO", "").strip()
    if email:
        params["mailto"] = email
    data = _get_json("https://api.openalex.org/works?" + urlencode(params))
    rows = []
    for item in data.get("results", []):
        title = item.get("display_name")
        location = item.get("primary_location") or {}
        source_info = location.get("source") or {}
        oa = item.get("open_access") or {}
        url = location.get("landing_page_url") or oa.get("oa_url") or item.get("doi") or item.get("id")
        if not title or not url:
            continue
        work_type = str(item.get("type") or "article").lower()
        resource_type = "Article" if work_type in {"article", "review"} else "Research Paper"
        authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
        topics = [topic.get("display_name", "") for topic in item.get("topics", [])[:6]]
        rows.append({
            "resource_id": f"openalex:{item.get('id', url)}", "title": title,
            "resource_type": resource_type, "author": ", ".join(filter(None, authors[:6])) or "Author not listed",
            "publisher": source_info.get("display_name"),
            "description": _openalex_abstract(item.get("abstract_inverted_index") or {}),
            "topics": topics, "publication_year": item.get("publication_year"),
            "source": "OpenAlex", "url": url,
            "availability": "Open access" if oa.get("is_oa") else "Publisher access may be required",
        })
    return rows


def _zenodo_records(subject: str) -> List[Dict[str, Any]]:
    params = {"q": subject, "size": 8}
    data = _get_json("https://zenodo.org/api/records/?" + urlencode(params))
    hits = (data.get("hits") or {}).get("hits", [])
    rows = []
    for item in hits:
        metadata = item.get("metadata") or {}
        title = metadata.get("title")
        url = (item.get("links") or {}).get("html") or item.get("doi_url")
        if not title or not url:
            continue
        kind = (metadata.get("resource_type") or {}).get("title", "").lower()
        authors = [author.get("name", "") for author in metadata.get("creators", [])]
        rows.append({
            "resource_id": f"zenodo:{item.get('id', url)}", "title": title,
            "resource_type": "Practical Resource" if any(term in kind for term in ("dataset", "software", "lesson", "learning object")) else "Research Paper",
            "author": ", ".join(filter(None, authors[:6])) or "Creator not listed",
            "publisher": "Zenodo", "description": _clean(metadata.get("description", "")),
            "topics": metadata.get("keywords", []), "publication_year": str(metadata.get("publication_date", ""))[:4] or None,
            "source": "Zenodo", "url": url,
            "availability": "Published record; check record for files and license",
        })
    return rows


def _youtube_videos(subject: str) -> List[Dict[str, Any]]:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    params = {"part": "snippet", "type": "video", "maxResults": 6, "q": subject, "key": key}
    data = _get_json("https://www.googleapis.com/youtube/v3/search?" + urlencode(params))
    rows = []
    for item in data.get("items", []):
        snippet = item.get("snippet") or {}
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id or not snippet.get("title"):
            continue
        rows.append({
            "resource_id": f"youtube:{video_id}", "title": snippet["title"],
            "resource_type": "Video", "author": snippet.get("channelTitle", "Channel not listed"),
            "publisher": snippet.get("channelTitle"), "description": _clean(snippet.get("description", "")),
            "topics": [], "publication_year": str(snippet.get("publishedAt", ""))[:4] or None,
            "source": "YouTube", "url": f"https://www.youtube.com/watch?v={video_id}",
            "availability": "Open video page; access depends on the publisher",
        })
    return rows


def discover_resources(subject: str) -> Dict[str, Any]:
    query = " ".join(subject.split())
    if len(query) < 2 or len(query) > 160:
        raise ValueError("Subject must be between 2 and 160 characters")
    sources = [("Google Books", _google_books), ("OpenAlex", _openalex_works), ("Zenodo", _zenodo_records)]
    if os.getenv("YOUTUBE_API_KEY", "").strip():
        sources.append(("YouTube", _youtube_videos))
    resources = []
    errors = []
    for name, search in sources:
        try:
            resources.extend(search(query))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
            errors.append({"source": name, "message": f"{name} search is temporarily unavailable ({type(exc).__name__})."})
    unique = {}
    for row in resources:
        unique.setdefault(row["resource_id"], row)
    if not unique and errors:
        raise RuntimeError("Resource catalogs are temporarily unavailable")
    return {"subject": query, "resources": list(unique.values()), "source_errors": errors}


def save_designer_resource(user_id: str, resource: Dict[str, Any]) -> Dict[str, Any]:
    resource_id = str(resource.get("resource_id", "")).strip()
    url = str(resource.get("url", "")).strip()
    if not resource_id or not url.startswith("https://"):
        raise ValueError("A valid discovered resource and HTTPS URL are required")
    curriculum_id = str(resource.get("curriculum_id", "")).strip()
    if curriculum_id:
        owned_curriculum = get_designer_metadata_collection().find_one({
            "source_type": "submitted_curriculum", "owner_id": user_id,
            "curriculum_id": curriculum_id, "status": "Active",
        }, {"_id": 1})
        if not owned_curriculum:
            raise LookupError("Curriculum is not available to this Designer")
    row = {
        "resource_id": resource_id,
        "title": str(resource.get("title", "")).strip()[:300],
        "resource_type": str(resource.get("resource_type", "")).strip()[:40],
        "author": str(resource.get("author", "")).strip()[:500],
        "publisher": str(resource.get("publisher", "")).strip()[:300],
        "description": str(resource.get("description", "")).strip()[:1000],
        "topics": [str(topic)[:120] for topic in resource.get("topics", [])[:20]],
        "publication_year": resource.get("publication_year"),
        "source": str(resource.get("source", "")).strip()[:100],
        "url": url,
        "availability": str(resource.get("availability", "")).strip()[:200],
        "subject": str(resource.get("subject", "")).strip()[:160],
        "curriculum_id": curriculum_id or None,
        "saved_at": datetime.now(timezone.utc),
    }
    db = get_workflow_database()
    user = db.users.find_one({"user_id": user_id}, {"saved_resources": 1})
    if not user:
        raise LookupError("Designer account not found")
    if any(item.get("resource_id") == resource_id for item in user.get("saved_resources", [])):
        return next(item for item in user["saved_resources"] if item.get("resource_id") == resource_id)
    db.users.update_one(
        {"user_id": user_id, "saved_resources.resource_id": {"$ne": resource_id}},
        {"$push": {"saved_resources": row}},
    )
    return row


def get_designer_saved_resources(user_id: str) -> List[Dict[str, Any]]:
    user = get_workflow_database().users.find_one({"user_id": user_id}, {"saved_resources": 1}) or {}
    return sorted(user.get("saved_resources", []), key=lambda item: item.get("saved_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def remove_designer_resource(user_id: str, resource_id: str) -> bool:
    result = get_workflow_database().users.update_one(
        {"user_id": user_id}, {"$pull": {"saved_resources": {"resource_id": resource_id}}}
    )
    return result.modified_count > 0


def record_resource_search(user_id: str, subject: str) -> None:
    get_workflow_database().users.update_one(
        {"user_id": user_id},
        {"$push": {"resource_search_history": {"$each": [{"subject": subject, "searched_at": datetime.now(timezone.utc)}], "$slice": -12}}},
    )


def get_resource_search_history(user_id: str) -> List[Dict[str, Any]]:
    user = get_workflow_database().users.find_one({"user_id": user_id}, {"resource_search_history": 1}) or {}
    return list(reversed(user.get("resource_search_history", [])))
