import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.data.database import (
    get_aicte_collection,
    get_aicte_metadata_collection,
    get_designer_collection,
    get_designer_metadata_collection,
)


AICTE_REFERENCE = "aicte_reference"
SUBMITTED_CURRICULUM = "submitted_curriculum"


def generate_document_id(file_bytes: bytes) -> str:
    return f"doc_{hashlib.sha256(file_bytes).hexdigest()}"


def _collections(source_type: str):
    if source_type == AICTE_REFERENCE:
        return get_aicte_collection(), get_aicte_metadata_collection()
    if source_type == SUBMITTED_CURRICULUM:
        return get_designer_collection(), get_designer_metadata_collection()
    raise ValueError(f"Unsupported source_type: {source_type}")


def _ownership_query(
    source_type: str,
    owner_id: Optional[str],
    *,
    include_legacy_aicte: bool = False,
) -> Dict[str, Any]:
    if source_type == AICTE_REFERENCE and include_legacy_aicte:
        # This collection belongs exclusively to the AICTE Admin store. Records
        # created before source_type was introduced remain official uploads.
        return {
            "$or": [
                {"source_type": AICTE_REFERENCE},
                {"source_type": {"$exists": False}},
            ]
        }
    query: Dict[str, Any] = {"source_type": source_type}
    if source_type == SUBMITTED_CURRICULUM:
        if not owner_id:
            raise ValueError("Authenticated owner_id is required for submitted curricula")
        query["owner_id"] = owner_id
    return query


def is_document_indexed(
    filename: str,
    *,
    source_type: str = AICTE_REFERENCE,
    owner_id: Optional[str] = None,
) -> Optional[int]:
    _, metadata_collection = _collections(source_type)
    existing_doc = metadata_collection.find_one(
        {
            "filename": filename,
            **_ownership_query(
                source_type,
                owner_id,
                include_legacy_aicte=True,
            ),
        }
    )
    if existing_doc:
        return int(existing_doc.get("total_chunks", 0))
    return None


def register_document(
    filename: str,
    total_chunks: int,
    *,
    document_id: str,
    source_type: str,
    programme: str,
    branch: str,
    curriculum_id: Optional[str] = None,
    year: Optional[int] = None,
    version: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> None:
    _, metadata_collection = _collections(source_type)
    ownership = _ownership_query(source_type, owner_id)
    record = {
        "filename": filename,
        "document_id": document_id,
        "source_type": source_type,
        "programme": programme,
        "branch": branch,
        "curriculum_id": curriculum_id,
        "year": year,
        "version": version,
        "total_chunks": total_chunks,
        "status": "Active",
        "uploaded_at": datetime.now(timezone.utc),
        **ownership,
    }
    metadata_collection.update_one(
        {"filename": filename, **ownership},
        {
            "$set": record
        },
        upsert=True,
    )


def get_all_documents(
    *,
    source_type: str = AICTE_REFERENCE,
    owner_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _, metadata_collection = _collections(source_type)
    docs = metadata_collection.find(
        _ownership_query(
            source_type,
            owner_id,
            include_legacy_aicte=True,
        ),
        {
            "_id": 0,
            "filename": 1,
            "document_id": 1,
            "source_type": 1,
            "programme": 1,
            "branch": 1,
            "curriculum_id": 1,
            "year": 1,
            "version": 1,
            "uploaded_at": 1,
            "total_chunks": 1,
            "status": 1,
        },
    ).sort("uploaded_at", -1)
    return list(docs)


def delete_document(
    filename: str,
    *,
    source_type: str = AICTE_REFERENCE,
    owner_id: Optional[str] = None,
) -> bool:
    vector_collection, metadata_collection = _collections(source_type)
    ownership = _ownership_query(source_type, owner_id)
    metadata_scope = _ownership_query(
        source_type,
        owner_id,
        include_legacy_aicte=True,
    )
    if source_type == AICTE_REFERENCE:
        top_level_scope = metadata_scope
        nested_scope = {
            "$or": [
                {"metadata.source_type": AICTE_REFERENCE},
                {"metadata.source_type": {"$exists": False}},
            ]
        }
    else:
        top_level_scope = ownership
        nested_scope = {
            f"metadata.{key}": value for key, value in ownership.items()
        }
    vector_collection.delete_many(
        {"metadata.source": filename, **nested_scope}
    )
    vector_collection.delete_many({"source": filename, **top_level_scope})

    result = metadata_collection.delete_one(
        {"filename": filename, **metadata_scope}
    )
    return result.deleted_count > 0
