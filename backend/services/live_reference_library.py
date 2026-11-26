"""Optional supplemental AICTE corpus shared by the importer and live retrieval."""
from backend.core.config import get_settings
from backend.data.database import get_aicte_database
from backend.services.rag_service import _make_vectorstore

COLLECTION = "live_aicte_reference_documents"
PRIVATE_INDEX = "live_curriculum_owner_index"


def supplement_collection():
    return get_aicte_database()[COLLECTION]


def retrieve_supplement(query):
    collection = supplement_collection()
    document_ids = list(collection.distinct("document_id", {"kind": "manifest"}))
    if not document_ids:
        return []
    return _make_vectorstore(
        collection, get_settings().aicte_mongodb_vector_index
    ).similarity_search(
        query, k=6, pre_filter={"document_id": {"$in": document_ids}},
    )
