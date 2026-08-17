import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = None
collection = None


def get_db():
    global client, db

    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI must be set in .env")

    if client is None:
        client = MongoClient(mongo_uri)
        db = client["rag_database"]

    return db

def get_collection():
    return get_db()["documents"]


def get_metadata_collection():
    return get_db()["documents_metadata"]