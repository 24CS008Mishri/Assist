from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.data.database import get_collection, get_metadata_collection


def is_document_indexed(filename: str) -> Optional[int]:
    existing_doc = get_metadata_collection().find_one({"filename": filename})
    if existing_doc:
        return int(existing_doc.get("total_chunks", 0))
    return None


def register_document(filename: str, total_chunks: int) -> None:
    get_metadata_collection().update_one(
        {"filename": filename},
        {
            "$set": {
                "filename": filename,
                "total_chunks": total_chunks,
                "status": "Active",
                "uploaded_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def get_all_documents() -> List[Dict[str, Any]]:
    docs = get_metadata_collection().find(
        {},
        {"_id": 0, "filename": 1, "uploaded_at": 1, "total_chunks": 1, "status": 1},
    ).sort("uploaded_at", -1)
    return list(docs)


def delete_document(filename: str) -> bool:
    vector_collection = get_collection()
    vector_collection.delete_many({"metadata.source": filename})
    vector_collection.delete_many({"source": filename})

    result = get_metadata_collection().delete_one({"filename": filename})
    return result.deleted_count > 0
