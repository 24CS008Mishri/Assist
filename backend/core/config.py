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

    groq_api_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "gpt-oss-20b")

    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "800"))
    chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
    retrieval_k = int(os.getenv("RAG_RETRIEVAL_K", "5"))

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
