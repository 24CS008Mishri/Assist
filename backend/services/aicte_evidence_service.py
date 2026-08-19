import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.core.analyzer_criteria import (
    AICTE_MANDATORY,
    AICTE_MODEL_REFERENCE,
    LOW_EVALUATION_COVERAGE_THRESHOLD,
)
from backend.data.database import get_aicte_collection
from backend.models.analyzer_scoring_schemas import (
    AicteEvidenceReference,
    AnalyzerScore,
    CheckStatus,
    ScoringCheck,
)


KNOWN_AICTE_SOURCE_FILENAMES: Tuple[str, ...] = (
    "Updated-AICTE - UG CSE.pdf",
)

AICTE_REFERENCE_UNAVAILABLE_MESSAGE = (
    "Official AICTE reference documents are not currently available. "
    "AICTE-based compliance evaluation cannot be completed."
)
AICTE_CHECK_EVIDENCE_UNAVAILABLE_REASON = (
    "Official AICTE reference evidence for this check is unavailable."
)

# Search phrases are explanatory retrieval hints only. They never participate
# in marks or score calculations.
AICTE_EVIDENCE_TERMS: Dict[str, Tuple[str, ...]] = {
    "structure.semesters": ("eight semesters", "semester viii", "course structure"),
    "structure.total_credits": ("163 credits", "range of credits", "general course structure"),
    "structure.category_distribution": ("humanities and social sciences", "basic science", "engineering science"),
    "structure.professional_core": ("professional core courses", "59 credits"),
    "structure.professional_elective": ("professional elective", "12 credits"),
    "structure.open_elective": ("open elective", "9 credits"),
    "structure.project_internship": ("project seminar internship", "project work", "internship"),
    "compliance.induction": ("induction programme", "student induction"),
    "compliance.environment": ("environmental sciences", "environmental studies"),
    "compliance.constitution_ikt": ("constitution of india", "indian knowledge tradition"),
    "compliance.human_values": ("universal human values", "human values"),
    "compliance.mandatory_non_credit": ("mandatory courses", "non credit", "zero credit"),
    "compliance.internship": ("internship", "industrial training"),
    "compliance.project": ("project work", "project seminar"),
    "compliance.essential_core": ("professional core courses", "computer science and engineering"),
    "skills.programming": ("programming for problem solving", "programming"),
    "skills.data_structures_algorithms": ("data structures", "design and analysis of algorithms"),
    "skills.mathematical_foundations": ("discrete mathematics", "mathematics"),
    "skills.computer_architecture": ("computer organization", "computer architecture"),
    "skills.operating_systems": ("operating systems",),
    "skills.databases": ("database management systems", "database systems"),
    "skills.computer_networks": ("computer networks",),
    "skills.theory_computation": ("theory of computation",),
    "skills.compiler_processing": ("compiler design", "compiler"),
    "skills.machine_learning_data": ("machine learning", "data science"),
    "skills.cyber_security": ("cyber security", "information security"),
}

_AICTE_CHUNK_QUERY: Dict[str, Any] = {
    "$or": [
        {
            "$and": [
                {
                    "$or": [
                        {"source_type": "aicte_reference"},
                        {"metadata.source_type": "aicte_reference"},
                    ]
                },
                {
                    "$or": [
                        {"programme": "B.Tech"},
                        {"metadata.programme": "B.Tech"},
                    ]
                },
                {
                    "$or": [
                        {"branch": "CSE"},
                        {"metadata.branch": "CSE"},
                    ]
                },
            ]
        },
        {
            "$and": [
                {"source_type": {"$exists": False}},
                {"metadata.source_type": {"$exists": False}},
                {"programme": {"$exists": False}},
                {"metadata.programme": {"$exists": False}},
                {"branch": {"$exists": False}},
                {"metadata.branch": {"$exists": False}},
            ]
        },
    ]
}

_AICTE_CHUNK_PROJECTION = {
    "_id": 0,
    "text": 1,
    "source": 1,
    "page_number": 1,
    "chunk_index": 1,
    "heading": 1,
    "metadata.source": 1,
    "metadata.page_number": 1,
    "metadata.chunk_index": 1,
    "metadata.heading": 1,
}


def _metadata_value(chunk: Mapping[str, Any], key: str) -> Any:
    if key in chunk and chunk.get(key) is not None:
        return chunk.get(key)
    metadata = chunk.get("metadata")
    return metadata.get(key) if isinstance(metadata, Mapping) else None


def _optional_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _load_aicte_chunks(collection: Any) -> List[Mapping[str, Any]]:
    cursor = collection.find(_AICTE_CHUNK_QUERY, _AICTE_CHUNK_PROJECTION)
    if hasattr(cursor, "limit"):
        cursor = cursor.limit(1000)
    return [chunk for chunk in cursor if _clean_text(chunk.get("text"))]


def _terms_for_check(check: ScoringCheck) -> Tuple[str, ...]:
    configured = AICTE_EVIDENCE_TERMS.get(check.check_id, ())
    expected = check.expected
    expected_terms: Sequence[str]
    if isinstance(expected, str):
        expected_terms = (expected,)
    elif isinstance(expected, (int, float)):
        expected_terms = (str(expected),)
    elif isinstance(expected, Mapping):
        expected_terms = tuple(str(key) for key in expected)
    else:
        expected_terms = ()
    return tuple(dict.fromkeys((*configured, check.title, *expected_terms)))


def _term_score(text: str, terms: Sequence[str]) -> int:
    normalized = text.casefold()
    score = 0
    for position, term in enumerate(terms):
        cleaned = _clean_text(term).casefold()
        if cleaned and cleaned in normalized:
            score += max(1, len(cleaned.split())) * (4 if position < 3 else 1)
    return score


def _chunk_sort_key(
    ranked: Tuple[int, Mapping[str, Any]],
) -> Tuple[int, int, int, str]:
    score, chunk = ranked
    page = _optional_int(_metadata_value(chunk, "page_number"))
    index = _optional_int(_metadata_value(chunk, "chunk_index"))
    source = _clean_text(_metadata_value(chunk, "source"))
    return (-score, page if page is not None else 10**9, index if index is not None else 10**9, source)


def _evidence_for_check(
    check: ScoringCheck,
    chunks: Iterable[Mapping[str, Any]],
    limit: int = 2,
) -> List[AicteEvidenceReference]:
    terms = _terms_for_check(check)
    ranked = [
        (score, chunk)
        for chunk in chunks
        if (score := _term_score(_clean_text(chunk.get("text")), terms)) > 0
    ]
    ranked.sort(key=_chunk_sort_key)
    evidence: List[AicteEvidenceReference] = []
    seen = set()
    for _, chunk in ranked:
        source = _clean_text(_metadata_value(chunk, "source")) or "Indexed AICTE reference"
        excerpt = _clean_text(chunk.get("text"))[:700]
        page = _optional_int(_metadata_value(chunk, "page_number"))
        index = _optional_int(_metadata_value(chunk, "chunk_index"))
        heading = _clean_text(_metadata_value(chunk, "heading")) or None
        key = (source, page, index, excerpt)
        if key in seen:
            continue
        seen.add(key)
        evidence.append(
            AicteEvidenceReference(
                source=source,
                page_number=page,
                chunk_index=index,
                heading=heading,
                excerpt=excerpt,
            )
        )
        if len(evidence) >= limit:
            break
    return evidence


def _round(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def _recalculate_score(score: AnalyzerScore) -> None:
    for criterion in score.criteria:
        evaluable = [
            check for check in criterion.checks if check.obtained_marks is not None
        ]
        obtained = sum(check.obtained_marks or 0.0 for check in evaluable)
        maximum = sum(check.maximum_marks for check in evaluable)
        criterion.obtained_marks = _round(obtained)
        criterion.evaluable_maximum_marks = _round(maximum)
        criterion.score = _round(obtained / maximum * 100) if maximum else None
        criterion.evaluation_coverage = (
            _round(maximum / criterion.configured_maximum_marks * 100)
            if criterion.configured_maximum_marks
            else 0.0
        )
        criterion.low_coverage = (
            criterion.evaluation_coverage < LOW_EVALUATION_COVERAGE_THRESHOLD
        )

    evaluable_criteria = [
        criterion for criterion in score.criteria if criterion.score is not None
    ]
    score.evaluable_weight = _round(
        sum(criterion.weight for criterion in evaluable_criteria)
    )
    total_weight = sum(criterion.weight for criterion in score.criteria)
    score.overall_evaluation_coverage = (
        _round(
            sum(
                criterion.evaluation_coverage * criterion.weight
                for criterion in score.criteria
            )
            / total_weight
        )
        if total_weight
        else 0.0
    )
    score.low_coverage = (
        score.overall_evaluation_coverage < LOW_EVALUATION_COVERAGE_THRESHOLD
    )
    score.overall_score = (
        _round(
            sum(
                criterion.score * criterion.weight
                for criterion in evaluable_criteria
            )
            / score.evaluable_weight
        )
        if score.evaluable_weight
        else None
    )


def _exclude_aicte_check(check: ScoringCheck, reason: str) -> None:
    check.status = CheckStatus.NOT_EVALUABLE
    check.obtained_marks = None
    check.aicte_evidence = []
    check.deduction_reason = reason


def enrich_score_with_aicte_evidence(
    score: AnalyzerScore,
    collection: Any = None,
) -> AnalyzerScore:
    """Require uploaded AICTE chunks for every AICTE-dependent score check."""
    enriched = score.model_copy(deep=True)
    try:
        resolved_collection = (
            collection if collection is not None else get_aicte_collection()
        )
        chunks = _load_aicte_chunks(resolved_collection)
    except Exception:
        enriched.aicte_reference_available = False
        enriched.aicte_reference_message = AICTE_REFERENCE_UNAVAILABLE_MESSAGE
        for criterion in enriched.criteria:
            for check in criterion.checks:
                if check.rule_type in {AICTE_MANDATORY, AICTE_MODEL_REFERENCE}:
                    _exclude_aicte_check(check, AICTE_REFERENCE_UNAVAILABLE_MESSAGE)
        _recalculate_score(enriched)
        enriched.overall_score = None
        return enriched

    enriched.aicte_reference_available = bool(chunks)
    enriched.aicte_reference_message = (
        None if chunks else AICTE_REFERENCE_UNAVAILABLE_MESSAGE
    )

    for criterion in enriched.criteria:
        for check in criterion.checks:
            if check.rule_type not in {
                AICTE_MANDATORY,
                AICTE_MODEL_REFERENCE,
            }:
                continue
            evidence = _evidence_for_check(check, chunks)
            if evidence:
                check.aicte_evidence = evidence
            else:
                reason = (
                    AICTE_CHECK_EVIDENCE_UNAVAILABLE_REASON
                    if chunks
                    else AICTE_REFERENCE_UNAVAILABLE_MESSAGE
                )
                _exclude_aicte_check(check, reason)
    _recalculate_score(enriched)
    if not enriched.aicte_reference_available:
        # Curriculum-only checks remain visible, but they must not be presented
        # as an overall AICTE compliance score.
        enriched.overall_score = None
    return enriched
