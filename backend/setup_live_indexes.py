"""Create the two Atlas vector indexes used by live curriculum consultations."""
import argparse

from pymongo.errors import CollectionInvalid, PyMongoError
from pymongo.operations import SearchIndexModel

from backend.core.config import get_settings
from backend.data.database import get_aicte_collection, get_designer_collection
from backend.services.live_reference_library import PRIVATE_INDEX, supplement_collection


def ensure_vector_index(collection, name, fields):
    existing = next(collection.list_search_indexes(name), None)
    if existing:
        defined = existing.get("latestDefinition", {}).get("fields", [])
        if {tuple(sorted(item.items())) for item in defined} != {tuple(sorted(item.items())) for item in fields}:
            raise ValueError(f"{name} has a different definition. Review it in Atlas before proceeding.")
        print(f"{name}: {existing.get('status', 'exists')}")
        return
    collection.create_search_index(SearchIndexModel(
        name=name, type="vectorSearch", definition={"fields": fields},
    ))
    print(f"{name}: requested; wait for READY in Atlas.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    settings = get_settings()
    try:
        baseline = next(get_aicte_collection().list_search_indexes(settings.aicte_mongodb_vector_index), None)
        fields = (baseline or {}).get("latestDefinition", {}).get("fields", [])
        vector = next((field for field in fields if field.get("type") == "vector" and field.get("path") == "embedding"), None)
        if vector is None:
            raise ValueError("The official Atlas index definition could not be read. Verify the configured index in Atlas.")
        for collection, name, paths in (
            (supplement_collection(), settings.aicte_mongodb_vector_index, ("document_id",)),
            (get_designer_collection(), PRIVATE_INDEX, ("owner_id", "document_id")),
        ):
            try:
                collection.database.create_collection(collection.name, check_exists=False)
            except CollectionInvalid:
                pass
            except PyMongoError as exc:
                if getattr(exc, "code", None) != 48:  # NamespaceExists
                    raise
            filters = [{"type": "filter", "path": path} for path in paths]
            ensure_vector_index(collection, name, [vector, *filters])
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except (RuntimeError, PyMongoError) as exc:
        parser.exit(1, f"Could not create Atlas indexes ({type(exc).__name__}, code {getattr(exc, 'code', None)}). Check network and search-index privileges.\n")


if __name__ == "__main__":
    main()
