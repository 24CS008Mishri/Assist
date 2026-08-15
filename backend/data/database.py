import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = None
collection = None


def get_collection():
    global client, collection

    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI must be set in .env")

    if collection is None:
        client = MongoClient(mongo_uri)
        db = client["rag_database"]
        collection = db["documents"]

    return collection
