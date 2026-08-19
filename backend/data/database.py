from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from backend.core.config import get_settings


def _connect(uri: str, environment_name: str) -> MongoClient:
    if not uri:
        raise RuntimeError(
            f"{environment_name} must be set before using this MongoDB service"
        )
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        client.close()
        raise RuntimeError(
            f"Unable to connect using {environment_name}. Verify that the Atlas "
            "cluster is active, the current IP is in its Network Access list, "
            "and the database user is valid."
        ) from exc
    return client


@lru_cache(maxsize=1)
def get_designer_client() -> MongoClient:
    return _connect(
        get_settings().curriculum_mongodb_uri,
        "CURRICULUM_MONGODB_URI",
    )


@lru_cache(maxsize=1)
def get_aicte_client() -> MongoClient:
    return _connect(get_settings().aicte_mongodb_uri, "AICTE_MONGODB_URI")


def get_designer_database() -> Database:
    return get_designer_client()[get_settings().curriculum_mongodb_db_name]


def get_aicte_database() -> Database:
    return get_aicte_client()[get_settings().aicte_mongodb_db_name]


def get_designer_collection() -> Collection:
    settings = get_settings()
    return get_designer_database()[settings.curriculum_mongodb_vector_collection]


def get_aicte_collection() -> Collection:
    settings = get_settings()
    return get_aicte_database()[settings.aicte_mongodb_vector_collection]


def get_designer_metadata_collection() -> Collection:
    settings = get_settings()
    return get_designer_database()[settings.curriculum_mongodb_metadata_collection]


def get_aicte_metadata_collection() -> Collection:
    settings = get_settings()
    return get_aicte_database()[settings.aicte_mongodb_metadata_collection]


# Compatibility aliases keep older Designer-only callers on the existing URI.
def get_client() -> MongoClient:
    return get_designer_client()


def get_db() -> Database:
    return get_designer_database()


def get_collection() -> Collection:
    return get_designer_collection()


def get_metadata_collection() -> Collection:
    return get_designer_metadata_collection()
