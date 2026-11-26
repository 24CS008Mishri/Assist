"""Session-time curriculum facts built from owned indexed PDF pages."""
from collections import defaultdict

from pymongo.errors import ExecutionTimeout

from backend.services.curriculum_extraction_service import (
    AmbiguousCurriculumError,
    CurriculumNotFoundError,
    InvalidCurriculumMetadataError,
    extract_structured_curriculum,
)


def curriculum_facts(owner_id, record):
    try:
        curriculum = extract_structured_curriculum(
            owner_id=owner_id, curriculum_id=record["curriculum_id"],
            document_id=record["document_id"],
        )
    except (AmbiguousCurriculumError, CurriculumNotFoundError, InvalidCurriculumMetadataError, ExecutionTimeout):
        # The retrieval excerpts still cover formats the table parser cannot read.
        return {"document": record["filename"], "structured_table_available": False}, []

    categories = defaultdict(float)
    for course in curriculum.courses:
        if course.category and course.credits is not None:
            categories[course.category] += course.credits
    pages = sorted({
        ref.page_number for semester in curriculum.semesters
        for ref in semester.evidence if ref.page_number is not None
    })
    return {
        "document": record["filename"],
        "structured_table_available": bool(curriculum.courses),
        "stated_programme_credits": curriculum.stated_total_credits,
        "sum_of_extracted_programme_credits": curriculum.calculated_total_credits,
        "category_credits_from_parsed_rows": dict(categories),
        "semesters": [
            {"semester": semester.semester_number, "stated_credits": semester.stated_total_credits,
             "sum_of_parsed_credits": semester.calculated_total_credits}
            for semester in curriculum.semesters
        ],
        "courses": [
            {"title": course.course_title, "semester": course.semester,
             "category": course.category, "credits": course.credits}
            for course in curriculum.courses[:180]
        ],
        "course_inventory_truncated": len(curriculum.courses) > 180,
        "parser_warnings": curriculum.extraction_warnings[:8],
        "table_pages": pages,
    }, pages
