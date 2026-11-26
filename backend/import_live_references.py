"""Inventory SIH reference PDFs and optionally index them for live consultations.

Run from Assist with: python -m backend.import_live_references <extracted SIH folder>
"""
import argparse
from pathlib import Path

from pymongo import ReplaceOne
from pymongo.errors import PyMongoError

from backend.data.database import get_aicte_metadata_collection
from backend.services.document_service import generate_document_id
from backend.services.live_reference_library import supplement_collection
from backend.services.pdf_service import extract_pages_from_pdf
from backend.services.rag_service import get_embeddings, get_text_splitter

# Titles/editions verified against each PDF's cover. A blank year denotes an
# edition that could not be established from the cover.
REFERENCES = {
    "AICTE Model Curriculum _UG_Civil_2024.pdf": ("B.Tech", "Civil", 2024, "Model curriculum"),
    "Automobile_final.pdf": ("B.Tech", "Automobile", 2020, "Model curriculum"),
    "B. Arch 2019_compressed.pdf": ("B.Arch", "Architecture", 2019, "Model curriculum"),
    "B. Plan with table of contents.pdf": ("B.Plan", "Planning", 2023, "Model curriculum"),
    "B.Tech Industrial Engineering.pdf": ("B.Tech", "Industrial", 2024, "Model curriculum"),
    "BBA Final.pdf": ("BBA", "Business Administration", 2024, "Model curriculum"),
    "BCA FINAL 24.09.2024 (2 year)_latest.pdf": ("BCA", "Computer Applications", 2024, "Draft model curriculum"),
    "biotechnology.pdf": ("B.Tech", "Biotechnology", 2020, "Model curriculum"),
    "CS (AI&ML).pdf": ("B.Tech", "CSE (AI and ML)", 2021, "Model curriculum"),
    "CS (AIDS).pdf": ("B.Tech", "CSE (AI and Data Science)", 2021, "Model curriculum"),
    "Draft Chemical Engineering Syllabus_latest.pdf": ("B.Tech", "Chemical", None, "Draft model curriculum"),
    "ELECTRICAL Engg Final.pdf": ("B.Tech", "Electrical", 2024, "Model curriculum"),
    "FINAL AICTE - UG-AUG 2018.pdf": ("B.Tech", "General", 2018, "Suggested reading"),
    "Final BTECH (L&SCM).pdf": ("B.Tech", "Logistics and Supply Chain", 2023, "Model curriculum"),
    "Final Updated - UG R & AI Curriculum 2023_latest.pdf": ("B.Tech", "Robotics and AI", 2023, "Model curriculum"),
    "Final_ECE.pdf": ("B.Tech", "ECE", 2023, "Revised model curriculum"),
    "Final_Mechanical Engg.pdf": ("B.Tech", "Mechanical", 2023, "Revised model curriculum"),
    "mechatronics.pdf": ("B.Tech", "Mechatronics", 2020, "Model curriculum"),
    "Revised Final VLSI_UG.pdf": ("B.Tech", "VLSI", 2023, "Revised model curriculum"),
    "Textile Engineering FINAL.pdf": ("B.Tech", "Textile", 2024, "Model curriculum"),
    "ug-vol1.pdf": ("B.Tech", "General", 2018, "Model curriculum, volume I"),
    "ug-vol2.pdf": ("B.Tech", "General", 2018, "Model curriculum, volume II"),
    "UG_Emerging.pdf": ("B.Tech", "Emerging Areas", 2019, "Model curriculum for emerging courses"),
    "Updated-AICTE - UG CSE.pdf": ("B.Tech", "CSE", 2022, "Revised model curriculum"),
}


def _apply_reference(collection, base, pages):
    splitter = get_text_splitter()
    pending = []
    chunk_index = 0

    def write_batch(batch):
        vectors = get_embeddings().embed_documents([row["text"] for row in batch])
        collection.bulk_write([
            ReplaceOne({"_id": row["_id"]}, {**row, "embedding": vector}, upsert=True)
            for row, vector in zip(batch, vectors, strict=True)
        ], ordered=False)

    for page in pages:
        for chunk in splitter.split_text(page.text):
            pending.append({
                **base, "_id": f'{base["document_id"]}:{chunk_index}', "kind": "chunk",
                "page_number": page.page_number, "chunk_index": chunk_index, "text": chunk,
            })
            chunk_index += 1
            if len(pending) == 64:
                write_batch(pending)
                pending.clear()
    if pending:
        write_batch(pending)
    collection.replace_one(
        {"_id": base["document_id"]},
        {**base, "_id": base["document_id"], "kind": "manifest", "total_chunks": chunk_index},
        upsert=True,
    )


def run(directory, apply=False):
    collection = supplement_collection() if apply else None
    originals = list(get_aicte_metadata_collection().find(
        {"$or": [{"source_type": "aicte_reference"}, {"source_type": {"$exists": False}}]},
        {"document_id": 1, "filename": 1, "total_chunks": 1},
    )) if apply else []
    originals = [row for row in originals if row.get("total_chunks", 0) > 0]
    known_hashes = {row.get("document_id") for row in originals}
    known_names = {str(row.get("filename") or "").casefold(): row for row in originals}
    for filename, (programme, branch, year, version) in REFERENCES.items():
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"Expected archive PDF is missing: {filename}")
        raw = path.read_bytes()
        document_id = generate_document_id(raw)
        pages = extract_pages_from_pdf(raw)
        label = f"{filename} | {programme} {branch} | {year or 'year unconfirmed'} | {version} | {len(pages)} readable pages"
        if not apply:
            print(label)
            continue
        existing = known_names.get(filename.casefold())
        if document_id in known_hashes or (existing and not existing.get("document_id")):
            print(f"Reusing existing reference: {filename}")
            continue
        if existing:
            print(f"Skipped filename collision with existing reference; review editions: {filename}")
            continue
        if collection.find_one({"_id": document_id}, {"_id": 1}):
            print(f"Already imported: {filename}")
            continue
        _apply_reference(collection, {
            "document_id": document_id, "source": filename, "source_type": "aicte_reference",
            "programme": programme, "branch": branch, "year": year, "version": version,
        }, pages)
        print(f"Imported: {label}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing the 24 SIH PDFs")
    parser.add_argument("--apply", action="store_true", help="Write missing references to the supplemental collection")
    options = parser.parse_args()
    try:
        run(options.directory, options.apply)
    except (RuntimeError, PyMongoError):
        parser.exit(1, "Atlas is unavailable or the MongoDB user cannot access the required collections.\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
