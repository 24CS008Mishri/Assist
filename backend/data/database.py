from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from backend.core.config import get_settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    settings = get_settings()
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI must be set before using MongoDB services")

    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    return client


def get_db() -> Database:
    return get_client()[get_settings().mongodb_db_name]


def get_collection() -> Collection:
    settings = get_settings()
    return get_db()[settings.mongodb_vector_collection]


def get_metadata_collection() -> Collection:
    settings = get_settings()
    return get_db()[settings.mongodb_metadata_collection]
