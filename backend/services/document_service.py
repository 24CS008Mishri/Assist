from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from backend.data.database import get_metadata_collection,get_collection


def is_document_indexed(filename: str) -> Optional[int]:
    """
    Checks if a document with the given filename has already been indexed.
    Returns total_chunks if found, otherwise None.
    """
    meta_coll = get_metadata_collection()
    existing_doc = meta_coll.find_one({"filename": filename})
    if existing_doc:
        return existing_doc.get("total_chunks", 0)
    return None


def register_document(filename: str, total_chunks: int) -> None:
    """Saves a new document entry in the metadata collection."""
    meta_coll = get_metadata_collection()
    meta_coll.insert_one({
        "filename": filename,
        "uploaded_at": datetime.now(timezone.utc),
        "total_chunks": total_chunks,
    })


def get_all_documents() -> List[Dict[str, Any]]:
    """Retrieves all indexed document records for the UI workspace library."""
    meta_coll = get_metadata_collection()
    return list(meta_coll.find({}, {"_id": 0, "filename": 1, "uploaded_at": 1, "total_chunks": 1}))


def delete_document(filename: str) -> bool:
    """
    Deletes the document's metadata entry and all corresponding 
    vector chunks from MongoDB Atlas Vector Search.
    """
    meta_coll = get_metadata_collection()
    vector_coll = get_collection()

    # 1. Delete vector embeddings (chunks) tagged with this filename source
    vector_coll.delete_many({"metadata.source": filename})

    # 2. Delete document entry from metadata collection
    result = meta_coll.delete_one({"filename": filename})

    return result.deleted_count > 0