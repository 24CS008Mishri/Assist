import os
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


class Settings:
    app_name = "Curriculum RAG Backend"
    api_prefix = "/api"

    mongodb_uri = os.getenv("MONGODB_URI", "")
    mongodb_db_name = os.getenv("MONGODB_DB_NAME", "rag_database")
    mongodb_vector_collection = os.getenv("MONGODB_VECTOR_COLLECTION", "documents")
    mongodb_metadata_collection = os.getenv("MONGODB_METADATA_COLLECTION", "documents_metadata")
    mongodb_vector_index = os.getenv("MONGODB_VECTOR_INDEX", "vector_index")

    # Official AICTE documents use the existing MONGODB_* store. AICTE_* names
    # remain optional overrides for deployments that explicitly separate them.
    aicte_mongodb_uri = os.getenv("AICTE_MONGODB_URI") or mongodb_uri
    aicte_mongodb_db_name = os.getenv("AICTE_DB_NAME") or mongodb_db_name
    aicte_mongodb_vector_collection = os.getenv(
        "AICTE_VECTOR_COLLECTION"
    ) or mongodb_vector_collection
    aicte_mongodb_metadata_collection = os.getenv(
        "AICTE_METADATA_COLLECTION"
    ) or mongodb_metadata_collection
    aicte_mongodb_vector_index = (
        os.getenv("AICTE_VECTOR_INDEX") or mongodb_vector_index
    )

    # Designer-owned curricula have their own MongoDB connection and namespace.
    # Fall back to MONGODB_* only for older deployments without the new variables.
    curriculum_mongodb_uri = os.getenv("CURRICULUM_MONGODB_URI") or mongodb_uri
    curriculum_mongodb_db_name = (
        os.getenv("CURRICULUM_MONGODB_DB_NAME") or mongodb_db_name
    )
    curriculum_mongodb_vector_collection = (
        os.getenv("CURRICULUM_MONGODB_VECTOR_COLLECTION")
        or mongodb_vector_collection
    )
    curriculum_mongodb_metadata_collection = (
        os.getenv("CURRICULUM_MONGODB_METADATA_COLLECTION")
        or mongodb_metadata_collection
    )
    curriculum_mongodb_vector_index = (
        os.getenv("CURRICULUM_MONGODB_VECTOR_INDEX") or mongodb_vector_index
    )

    groq_api_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "800"))
    chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
    retrieval_k = int(os.getenv("RAG_RETRIEVAL_K", "12"))
    retrieval_direct_k = int(os.getenv("RAG_RETRIEVAL_DIRECT_K", "8"))
    retrieval_fetch_k = int(os.getenv("RAG_RETRIEVAL_FETCH_K", "36"))
    retrieval_diversity = float(os.getenv("RAG_RETRIEVAL_DIVERSITY", "0.35"))
    rag_context_char_limit = int(os.getenv("RAG_CONTEXT_CHAR_LIMIT", "30000"))
    rag_answer_max_tokens = int(os.getenv("RAG_ANSWER_MAX_TOKENS", "1800"))

    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500",
        ).split(",")
        if origin.strip()
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
