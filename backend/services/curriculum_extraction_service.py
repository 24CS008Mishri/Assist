import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.data.database import get_designer_collection
from backend.models.analyzer_schemas import (
    Course,
    EvidenceReference,
    Semester,
    StructuredCurriculum,
)


class CurriculumExtractionError(RuntimeError):
    pass


class CurriculumNotFoundError(CurriculumExtractionError):
    pass


class AmbiguousCurriculumError(CurriculumExtractionError):
    pass


class InvalidCurriculumMetadataError(CurriculumExtractionError):
    pass


_NUMBER = r"\d+(?:\.\d+)?"
_COURSE_CODE = r"[A-Z]{1,6}(?:[-/]?[A-Z]{1,4})?[- ]?\d{2,4}[A-Z]?"
_CATEGORY_CODES = ("BSC", "ESC", "HSMC", "PCC", "PEC", "OEC", "MC")
_CATEGORY_PATTERN = "|".join(_CATEGORY_CODES)
_ROMAN_VALUES = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}

_SEMESTER_PATTERNS = (
    re.compile(r"\bsemester\s*[-:]?\s*(?P<value>[ivx]+|\d{1,2})\b", re.I),
    re.compile(r"\b(?P<value>[ivx]+|\d{1,2})\s*[-:]?\s*semester\b", re.I),
)
_COURSE_PREFIX = re.compile(
    rf"^\s*(?:(?P<category>{_CATEGORY_PATTERN})\s+)?"
    rf"(?P<code>{_COURSE_CODE})\s+(?P<body>.+?)\s*$",
    re.I,
)
_LTP_LABELLED = re.compile(
    rf"(?P<lecture>{_NUMBER})\s*L\s*[:/\-]?\s*"
    rf"(?P<tutorial>{_NUMBER})\s*T\s*[:/\-]?\s*"
    rf"(?P<practical>{_NUMBER})\s*P"
    rf"(?:\s*[:/\-]?\s*(?P<credits>{_NUMBER})\s*(?:C|credits?))?\s*$",
    re.I,
)
_LTPC_DASHED = re.compile(
    rf"(?:L\s*[-:]\s*T\s*[-:]\s*P\s*[-:]\s*C\s*[:=]?\s*)?"
    rf"(?P<lecture>{_NUMBER})\s*[-/]\s*"
    rf"(?P<tutorial>{_NUMBER})\s*[-/]\s*"
    rf"(?P<practical>{_NUMBER})\s*[-/]\s*"
    rf"(?P<credits>{_NUMBER})(?:\s*credits?)?\s*$",
    re.I,
)
_LTPC_SPACED = re.compile(
    rf"(?P<lecture>{_NUMBER})\s+"
    rf"(?P<tutorial>{_NUMBER})\s+"
    rf"(?P<practical>{_NUMBER})\s+"
    rf"(?P<credits>{_NUMBER})(?:\s*credits?)?\s*$",
    re.I,
)
_COURSE_HEADING = re.compile(
    rf"^\s*(?:course\s+code\s*[:\-]\s*)?"
    rf"(?P<code>{_COURSE_CODE})\s*(?:[:|]|\s-\s)\s*(?P<title>.+?)\s*$",
    re.I,
)
_COURSE_HEADING_PAREN = re.compile(
    rf"^\s*(?:subject\s*:\s*)?(?P<title>.+?)\s*"
    rf"\(\s*(?P<code>{_COURSE_CODE})\s*\)"
    rf"(?:\s*\([^)]*\))?\s*$",
    re.I,
)
_NON_COURSE_CODE = re.compile(
    r"^(?:PRACTICAL|EXPERIMENT|MODULE|UNIT|CHAPTER|CO|PO|PSO)\d+$",
    re.I,
)
_TEACHING_SCHEME_LABELS = {
    "theory": "lecture_hours",
    "lecture": "lecture_hours",
    "practical": "practical_hours",
    "tutorial": "tutorial_hours",
    "credit": "credits",
    "credits": "credits",
}

_HEADER_ALIASES = {
    "code": {"code", "coursecode", "subjectcode", "papercode"},
    "title": {
        "title",
        "coursetitle",
        "subject",
        "subjectname",
        "coursename",
        "paper",
    },
    "category": {"category", "coursecategory", "cat", "type"},
    "semester": {"semester", "sem"},
    "lecture_hours": {"l", "lecture", "lectures", "lecturehours"},
    "tutorial_hours": {"t", "tutorial", "tutorials", "tutorialhours"},
    "practical_hours": {
        "p",
        "practical",
        "practicals",
        "practicalhours",
        "lab",
        "laboratory",
    },
    "credits": {"c", "credit", "credits", "coursecredit"},
}

_CATEGORY_ALIASES = (
    (re.compile(r"\bBSC\b|basic\s+science", re.I), "BSC"),
    (re.compile(r"\bESC\b|engineering\s+science", re.I), "ESC"),
    (re.compile(r"\bHSMC\b|humanities.*(?:social|management)", re.I), "HSMC"),
    (re.compile(r"\bPCC\b|professional\s+core", re.I), "PCC"),
    (re.compile(r"\bPEC\b|professional\s+elective", re.I), "PEC"),
    (re.compile(r"\bOEC\b|open\s+elective", re.I), "OEC"),
    (re.compile(r"\buniversity\s+elective\b", re.I), "University Elective"),
    (re.compile(r"\bMC\b|mandatory\s+course", re.I), "MC"),
    (re.compile(r"\bproject\b", re.I), "Project"),
    (re.compile(r"\binternship\b|industrial\s+training", re.I), "Internship"),
)


def _metadata_value(chunk: Mapping[str, Any], key: str) -> Any:
    if key in chunk:
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


def _optional_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    match = re.fullmatch(_NUMBER, text)
    return float(text) if match else None


def _clean_line(line: str) -> str:
    line = line.replace("\x00", " ")
    line = re.sub(r"[\uf0b7\uf0fc\u2022]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def _clean_item(value: str) -> str:
    value = re.sub(r"^[\s\-•*]+", "", value)
    value = re.sub(r"^\(?\d+\)?[.)\-]\s*", "", value)
    return _clean_line(value)


def _is_semantic_artifact(line: str) -> bool:
    cleaned = _clean_line(line)
    if not cleaned:
        return True
    if re.fullmatch(r"Page\s+\d+(?:\s+of\s+\d+)?", cleaned, re.I):
        return True
    if re.fullmatch(_NUMBER, cleaned):
        return True
    return bool(
        re.fullmatch(
            r"(?:unit|no\.?|hrs?\.?|hours/week|marks?|teaching|scheme|"
            r"teaching\s+scheme|theory|lecture|practical|tutorial|"
            r"total|credit|credits|topic)",
            cleaned,
            re.I,
        )
    )


def _is_semantic_stop_heading(line: str) -> bool:
    return bool(
        re.match(
            r"^(?:"
            r"bridge\s+topics?(?:\s*/\s*self[- ]?study(?:\s*/\s*revisit)?)?"
            r"|self[- ]?study(?:\s*/\s*further\s+study)?"
            r"(?:\s+components?\s+and\s+materials?)?"
            r"|recommended\s+(?:study\s+)?materials?"
            r"|instructions?\s+to\s+subject\s+teachers?"
            r"|practical\s+lists?"
            r"|references?\s+books?"
            r"|subject\s*:"
            r")\s*:?\s*$",
            line,
            re.I,
        )
    )


def _evidence(
    chunk: Mapping[str, Any],
    excerpt: str,
    fields: Sequence[str],
) -> EvidenceReference:
    normalized = _clean_line(excerpt)
    return EvidenceReference(
        page_number=_optional_int(_metadata_value(chunk, "page_number")),
        chunk_index=_optional_int(_metadata_value(chunk, "chunk_index")),
        excerpt=normalized[:500],
        fields=list(dict.fromkeys(fields)),
    )


def _append_unique(items: List[str], value: str) -> None:
    cleaned = _clean_item(value)
    if cleaned and cleaned.lower() not in {item.lower() for item in items}:
        items.append(cleaned)


def _append_evidence(
    items: List[EvidenceReference], evidence: EvidenceReference
) -> None:
    key = (
        evidence.page_number,
        evidence.chunk_index,
        evidence.excerpt,
        tuple(evidence.fields),
    )
    if key not in {
        (item.page_number, item.chunk_index, item.excerpt, tuple(item.fields))
        for item in items
    }:
        items.append(evidence)


def _semester_value(value: str) -> Optional[int]:
    cleaned = value.strip().upper()
    number = int(cleaned) if cleaned.isdigit() else _ROMAN_VALUES.get(cleaned)
    return number if number is not None and 1 <= number <= 12 else None


def detect_semester_number(line: str) -> Optional[int]:
    for pattern in _SEMESTER_PATTERNS:
        match = pattern.search(line)
        if match:
            return _semester_value(match.group("value"))
    return None


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _header_role(value: str) -> Optional[str]:
    normalized = _normalized_header(value)
    for role, aliases in _HEADER_ALIASES.items():
        if normalized in aliases:
            return role
    return None


def _table_header(line: str) -> Optional[Dict[str, int]]:
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in line.split("|")]
    mapping = {
        role: index
        for index, cell in enumerate(cells)
        if (role := _header_role(cell)) is not None
    }
    required = {"title", "credits"}
    has_hours = any(
        field in mapping
        for field in ("lecture_hours", "tutorial_hours", "practical_hours")
    )
    return mapping if required.issubset(mapping) and has_hours else None


def _normalize_course_code(value: str) -> Optional[str]:
    cleaned = re.sub(r"\s+", "", value.strip().upper())
    if not re.fullmatch(_COURSE_CODE, cleaned, re.I):
        return None
    if _NON_COURSE_CODE.fullmatch(cleaned):
        return None
    return cleaned


def _explicit_category(value: str) -> Optional[str]:
    for pattern, category in _CATEGORY_ALIASES:
        if pattern.search(value):
            return category
    return None


def _is_special_title(title: str) -> bool:
    return bool(
        re.search(
            r"\b(project|internship|industrial\s+training|"
            r"professional\s+elective|open\s+elective|mandatory\s+course)\b",
            title,
            re.I,
        )
    )


def _course_evidence_fields(course: Course) -> List[str]:
    fields = ["course_title"]
    for field in (
        "course_code",
        "semester",
        "category",
        "lecture_hours",
        "tutorial_hours",
        "practical_hours",
        "credits",
    ):
        if getattr(course, field) is not None:
            fields.append(field)
    return fields


def _course_from_table_row(
    line: str,
    header: Mapping[str, int],
    current_semester: Optional[int],
    chunk: Mapping[str, Any],
) -> Optional[Course]:
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in line.split("|")]
    if not header or max(header.values()) >= len(cells):
        return None

    title = _clean_line(cells[header["title"]])
    code = (
        _normalize_course_code(cells[header["code"]])
        if "code" in header
        else None
    )
    category = (
        _explicit_category(cells[header["category"]])
        if "category" in header
        else None
    )
    category = category or _explicit_category(title)
    semester = current_semester
    if "semester" in header:
        semester = _semester_value(cells[header["semester"]]) or current_semester

    course = Course(
        course_code=code,
        course_title=title,
        semester=semester,
        category=category,
        lecture_hours=_optional_number(cells[header["lecture_hours"]])
        if "lecture_hours" in header
        else None,
        tutorial_hours=_optional_number(cells[header["tutorial_hours"]])
        if "tutorial_hours" in header
        else None,
        practical_hours=_optional_number(cells[header["practical_hours"]])
        if "practical_hours" in header
        else None,
        credits=_optional_number(cells[header["credits"]]),
    )
    if not title or (not code and not category and not _is_special_title(title)):
        return None
    if course.credits is None and all(
        value is None
        for value in (
            course.lecture_hours,
            course.tutorial_hours,
            course.practical_hours,
        )
    ):
        return None
    course.evidence.append(_evidence(chunk, line, _course_evidence_fields(course)))
    return course


def _course_from_unheaded_pipe_row(
    line: str,
    current_semester: Optional[int],
    chunk: Mapping[str, Any],
) -> Optional[Course]:
    if "|" not in line:
        return None
    cells = [cell.strip() for cell in line.split("|") if cell.strip()]
    if len(cells) < 6:
        return None

    category = _explicit_category(cells[0])
    code_index = 1 if category and len(cells) > 1 else 0
    code = _normalize_course_code(cells[code_index])
    if not code:
        return None

    numeric = [_optional_number(value) for value in cells[-4:]]
    if any(value is None for value in numeric):
        return None
    title_cells = cells[code_index + 1 : -4]
    if title_cells and _explicit_category(title_cells[0]):
        category = category or _explicit_category(title_cells.pop(0))
    title = _clean_line(" ".join(title_cells))
    if not title:
        return None
    category = category or _explicit_category(title)

    course = Course(
        course_code=code,
        course_title=title,
        semester=current_semester,
        category=category,
        lecture_hours=numeric[0],
        tutorial_hours=numeric[1],
        practical_hours=numeric[2],
        credits=numeric[3],
    )
    course.evidence.append(_evidence(chunk, line, _course_evidence_fields(course)))
    return course


def _course_from_text_row(
    line: str,
    current_semester: Optional[int],
    chunk: Mapping[str, Any],
) -> Optional[Course]:
    prefix = _COURSE_PREFIX.match(line)
    if not prefix:
        return None

    body = prefix.group("body")
    tail = None
    for pattern in (_LTP_LABELLED, _LTPC_DASHED, _LTPC_SPACED):
        tail = pattern.search(body)
        if tail:
            break
    if not tail:
        return None

    title = _clean_line(body[: tail.start()].strip(" -|:"))
    if not title:
        return None
    category = (
        _explicit_category(prefix.group("category"))
        if prefix.group("category")
        else None
    )
    if not category:
        leading_category = _explicit_category(title.split(" ", 1)[0])
        if leading_category in _CATEGORY_CODES:
            category = leading_category
            title = _clean_line(title.split(" ", 1)[1]) if " " in title else ""
    if not title:
        return None
    category = category or _explicit_category(title)

    course = Course(
        course_code=_normalize_course_code(prefix.group("code")),
        course_title=title,
        semester=current_semester,
        category=category,
        lecture_hours=_optional_number(tail.group("lecture")),
        tutorial_hours=_optional_number(tail.group("tutorial")),
        practical_hours=_optional_number(tail.group("practical")),
        credits=_optional_number(tail.groupdict().get("credits")),
    )
    course.evidence.append(_evidence(chunk, line, _course_evidence_fields(course)))
    return course


def _course_key(course: Course) -> Tuple[Any, ...]:
    if course.course_code:
        return ("code", course.course_code.upper(), course.semester)
    return (
        "title",
        course.course_title.lower(),
        course.semester,
        course.category,
    )


def _merge_course(target: Course, incoming: Course) -> Course:
    for field in (
        "course_code",
        "semester",
        "category",
        "lecture_hours",
        "tutorial_hours",
        "practical_hours",
        "credits",
    ):
        if getattr(target, field) is None and getattr(incoming, field) is not None:
            setattr(target, field, getattr(incoming, field))
    for field in (
        "prerequisites",
        "course_objectives",
        "course_outcomes",
        "modules",
        "topics",
        "assessment_information",
        "references",
    ):
        for value in getattr(incoming, field):
            _append_unique(getattr(target, field), value)
    for item in incoming.evidence:
        _append_evidence(target.evidence, item)
    return target


def _course_bucket(course: Course) -> str:
    title = course.course_title.lower()
    category = course.category
    if category == "Internship" or re.search(
        r"\binternship\b|industrial\s+training", title
    ):
        return "internships"
    if category == "Project" or re.search(r"\bproject\b", title):
        return "projects"
    if category == "PEC" or "professional elective" in title:
        return "professional_electives"
    if category == "OEC" or "open elective" in title:
        return "open_electives"
    if category == "MC" or "mandatory course" in title:
        return "mandatory_courses"
    return "courses"


def _split_values(value: str) -> List[str]:
    cleaned = _clean_item(value)
    if not cleaned or cleaned.lower() in {"none", "nil", "not applicable", "na", "n/a"}:
        return []
    return [
        item
        for part in re.split(r"[;,]", cleaned)
        if (item := _clean_item(part))
    ]


def _section_line(line: str) -> Optional[Tuple[str, str]]:
    patterns = (
        (
            "prerequisites",
            r"(?:course\s+)?pre[- ]?requisites?"
            r"(?:\s+(?:online\s+)?video\s*/?\s*courses?)?",
        ),
        ("course_objectives", r"course\s+objectives?"),
        ("course_outcomes", r"course\s+outcomes?"),
        ("topics", r"(?:topics?|syllabus)"),
        (
            "assessment_information",
            r"(?:assessment|evaluation\s+scheme|marks?\s+distribution)",
        ),
        (
            "references",
            r"(?:references?|text\s*books?|suggested\s+readings?)",
        ),
    )
    for section, heading in patterns:
        match = re.match(
            rf"^(?:{heading})\s*(?:[:\-]\s*(?P<value>.*))?$",
            line,
            re.I,
        )
        if match:
            return section, match.group("value") or ""
    return None


def _add_section_value(
    course: Course,
    section: str,
    value: str,
    chunk: Mapping[str, Any],
    original_line: str,
) -> None:
    cleaned = _clean_item(value)
    if _is_semantic_artifact(cleaned):
        return

    if section == "course_outcomes":
        outcome = re.match(r"^CO\s*(\d+)\s*[:.\-]\s*(.+)$", cleaned, re.I)
        if outcome:
            outcome_number = outcome.group(1)
            existing_index = next(
                (
                    index
                    for index, item in enumerate(course.course_outcomes)
                    if re.match(
                        rf"^CO\s*{re.escape(outcome_number)}\s*[:.\-]",
                        item,
                        re.I,
                    )
                ),
                None,
            )
            if existing_index is None:
                course.course_outcomes.append(cleaned)
            elif cleaned.startswith(course.course_outcomes[existing_index]):
                course.course_outcomes[existing_index] = cleaned
            _append_evidence(
                course.evidence,
                _evidence(chunk, original_line, [section]),
            )
            return

        if not course.course_outcomes:
            return
        if any(item.endswith(cleaned) for item in course.course_outcomes):
            return
        previous = course.course_outcomes[-1]
        if previous.endswith(cleaned):
            return
        separator = "" if previous.endswith("-") else " "
        course.course_outcomes[-1] = f"{previous}{separator}{cleaned}"
        _append_evidence(
            course.evidence,
            _evidence(chunk, original_line, [section]),
        )
        return

    if section == "prerequisites":
        for item in _split_values(cleaned):
            _append_unique(course.prerequisites, item)
    else:
        _append_unique(getattr(course, section), cleaned)
    _append_evidence(course.evidence, _evidence(chunk, original_line, [section]))


def _find_course_by_code(courses: Iterable[Course], code: str) -> Optional[Course]:
    normalized = _normalize_course_code(code)
    return next(
        (
            course
            for course in courses
            if course.course_code
            and _normalize_course_code(course.course_code) == normalized
        ),
        None,
    )


def _sort_chunks(chunks: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    maximum = 2**31 - 1

    def sort_value(chunk: Mapping[str, Any], field: str) -> int:
        value = _optional_int(_metadata_value(chunk, field))
        return value if value is not None else maximum

    return sorted(
        chunks,
        key=lambda chunk: (
            sort_value(chunk, "page_number"),
            sort_value(chunk, "chunk_index"),
        ),
    )


def load_submitted_curriculum_chunks(
    *,
    curriculum_id: Optional[str] = None,
    document_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    collection: Any = None,
) -> List[Mapping[str, Any]]:
    if not curriculum_id and not document_id:
        raise InvalidCurriculumMetadataError(
            "curriculum_id or document_id is required for extraction"
        )
    if not owner_id:
        raise InvalidCurriculumMetadataError(
            "Authenticated owner_id is required for curriculum extraction"
        )
    query: Dict[str, Any] = {
        "source_type": "submitted_curriculum",
        "owner_id": owner_id,
    }
    if curriculum_id:
        query["curriculum_id"] = curriculum_id
    if document_id:
        query["document_id"] = document_id

    vector_collection = collection or get_designer_collection()
    chunks = list(vector_collection.find(query, {"embedding": 0}))
    if not chunks:
        identity = curriculum_id or document_id
        raise CurriculumNotFoundError(
            f"No submitted curriculum chunks found for {identity}"
        )
    return _sort_chunks(chunks)


def _single_metadata_value(
    chunks: Sequence[Mapping[str, Any]],
    field: str,
    *,
    required: bool = False,
) -> Any:
    values = {
        value
        for chunk in chunks
        if (value := _metadata_value(chunk, field)) is not None
    }
    if len(values) > 1:
        raise AmbiguousCurriculumError(
            f"Multiple {field} values were found; specify a document_id"
        )
    if not values:
        if required:
            raise InvalidCurriculumMetadataError(
                f"Submitted curriculum chunks are missing {field}"
            )
        return None
    return next(iter(values))


def _explicit_credit_total(line: str) -> Optional[float]:
    if "credit" not in line.lower() or "total" not in line.lower():
        return None
    match = re.search(rf"({_NUMBER})\s*(?:credits?)?\s*$", line, re.I)
    return _optional_number(match.group(1)) if match else None


def _is_curriculum_total(line: str) -> bool:
    return bool(
        re.search(
            r"\b(grand|overall|programme|program|curriculum|degree)\b|"
            r"\bB\.?\s*Tech\b|\ball\s+semesters\b",
            line,
            re.I,
        )
    )


def _merge_overlapping_fragments(fragments: Sequence[str]) -> str:
    """Reconstruct page text when adjacent chunks contain exact overlap."""
    merged = ""
    for fragment in fragments:
        if not fragment:
            continue
        if not merged:
            merged = fragment
            continue
        overlap = 0
        maximum = min(len(merged), len(fragment))
        for size in range(maximum, 19, -1):
            if merged.endswith(fragment[:size]):
                overlap = size
                break
        merged = f"{merged}{fragment[overlap:]}" if overlap else f"{merged}\n{fragment}"
    return merged


def _columnar_scheme_totals(
    chunks: Sequence[Mapping[str, Any]],
) -> List[Tuple[Optional[int], float, EvidenceReference]]:
    """Extract only strongly identified totals from column-major scheme pages.

    PDF table extraction can emit each column top-to-bottom, destroying the row
    relationships needed to reconstruct individual courses safely. The final
    teaching-hours / credits / marks aggregate is still usable when its labels
    and numeric signature are all present on the same page.
    """
    pages: Dict[int, List[Mapping[str, Any]]] = {}
    for chunk in chunks:
        page_number = _optional_int(_metadata_value(chunk, "page_number"))
        if page_number is not None:
            pages.setdefault(page_number, []).append(chunk)

    totals: List[Tuple[Optional[int], float, EvidenceReference]] = []
    for page_chunks in pages.values():
        ordered = _sort_chunks(page_chunks)
        page_text = _merge_overlapping_fragments(
            [str(chunk.get("text") or chunk.get("page_content") or "") for chunk in ordered]
        )
        lowered = _clean_line(page_text).lower()
        required_labels = (
            "teaching scheme",
            "examination scheme",
            "credit",
            "total hours",
        )
        if not all(label in lowered for label in required_labels):
            continue

        numeric_lines: List[Tuple[str, float]] = []
        for raw_line in page_text.splitlines():
            line = _clean_line(raw_line)
            value = _optional_number(line)
            if value is not None:
                numeric_lines.append((line, value))
        if len(numeric_lines) < 3:
            continue

        tail = numeric_lines[-3:]
        teaching_hours, credits, marks = (value for _, value in tail)
        if not (
            0 < teaching_hours < 100
            and 0 < credits < 100
            and marks >= 100
            and marks > teaching_hours
            and marks > credits
        ):
            continue

        semester = next(
            (
                detected
                for line in page_text.splitlines()
                if (detected := detect_semester_number(line)) is not None
            ),
            None,
        )
        excerpt = " ".join(raw for raw, _ in tail)
        totals.append(
            (
                semester,
                credits,
                _evidence(ordered[-1], excerpt, ["semester_total_credits"]),
            )
        )
    return totals


def extract_structured_curriculum(
    curriculum_id: Optional[str] = None,
    *,
    document_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    collection: Any = None,
) -> StructuredCurriculum:
    chunks = load_submitted_curriculum_chunks(
        curriculum_id=curriculum_id,
        document_id=document_id,
        owner_id=owner_id,
        collection=collection,
    )

    resolved_curriculum_id = _single_metadata_value(
        chunks, "curriculum_id", required=True
    )
    resolved_document_id = _single_metadata_value(chunks, "document_id", required=True)
    programme = _single_metadata_value(chunks, "programme", required=True)
    branch = _single_metadata_value(chunks, "branch", required=True)
    if programme != "B.Tech" or branch != "CSE":
        raise InvalidCurriculumMetadataError(
            "Phase 2 extraction supports only programme=B.Tech and branch=CSE"
        )

    warnings: List[str] = []
    semesters: Dict[int, Semester] = {}
    course_map: Dict[Tuple[Any, ...], Course] = {}
    course_order: List[Course] = []
    curriculum_evidence: List[EvidenceReference] = []
    stated_total_credits: Optional[float] = None
    current_semester: Optional[int] = None
    current_course: Optional[Course] = None
    current_section: Optional[str] = None
    active_header: Optional[Dict[str, int]] = None
    scheme_lines_remaining = 0
    pending_scheme_field: Optional[Tuple[str, str]] = None
    scheme_page_number: Optional[int] = None
    current_page_number: Optional[int] = None

    def semester_record(
        number: int, evidence: Optional[EvidenceReference] = None
    ) -> Semester:
        if number not in semesters:
            semesters[number] = Semester(semester_number=number)
        if evidence:
            _append_evidence(semesters[number].evidence, evidence)
        return semesters[number]

    def add_course(course: Course) -> Course:
        key = _course_key(course)
        if key in course_map:
            return _merge_course(course_map[key], course)
        course_map[key] = course
        course_order.append(course)
        if course.semester is not None:
            semester_record(course.semester)
        return course

    def set_scheme_value(
        course: Course,
        field: str,
        label: str,
        raw_value: str,
        chunk: Mapping[str, Any],
    ) -> None:
        value = (
            0.0
            if re.fullmatch(r"[-–—]", raw_value)
            else _optional_number(raw_value)
        )
        if value is None:
            return
        existing = getattr(course, field)
        if existing is not None and existing != value:
            warnings.append(
                f"Conflicting {field.replace('_', ' ')} values were found for "
                f"{course.course_code or course.course_title}."
            )
            return
        setattr(course, field, value)
        _append_evidence(
            course.evidence,
            _evidence(chunk, f"{label} {raw_value}", [field]),
        )

    for chunk in chunks:
        chunk_page_number = _optional_int(_metadata_value(chunk, "page_number"))
        if (
            current_page_number is not None
            and chunk_page_number is not None
            and chunk_page_number != current_page_number
        ):
            current_section = None
        if chunk_page_number is not None:
            current_page_number = chunk_page_number
        text = str(chunk.get("text") or chunk.get("page_content") or "")
        raw_lines = text.splitlines()
        chunk_semester = next(
            (
                detected
                for raw_line in raw_lines
                if (detected := detect_semester_number(raw_line)) is not None
            ),
            None,
        )
        for raw_line in raw_lines:
            line = _clean_line(raw_line)
            if not line or re.fullmatch(r"Page\s+\d+", line, re.I):
                continue

            detected_semester = detect_semester_number(line)
            if detected_semester is not None:
                current_semester = detected_semester
                if (
                    current_course is not None
                    and current_course.semester != detected_semester
                ):
                    current_course = None
                current_section = None
                active_header = None
                semester_record(
                    detected_semester,
                    _evidence(chunk, line, ["semester_number"]),
                )

            explicit_total = _explicit_credit_total(line)
            if explicit_total is not None:
                total_evidence = _evidence(
                    chunk,
                    line,
                    [
                        "stated_total_credits"
                        if _is_curriculum_total(line)
                        else "semester_total_credits"
                    ],
                )
                if _is_curriculum_total(line) or current_semester is None:
                    if (
                        stated_total_credits is not None
                        and stated_total_credits != explicit_total
                    ):
                        warnings.append(
                            "Conflicting explicitly stated curriculum credit totals were found."
                        )
                    else:
                        stated_total_credits = explicit_total
                    _append_evidence(curriculum_evidence, total_evidence)
                else:
                    semester = semester_record(current_semester)
                    if (
                        semester.stated_total_credits is not None
                        and semester.stated_total_credits != explicit_total
                    ):
                        warnings.append(
                            f"Conflicting stated totals were found for semester {current_semester}."
                        )
                    else:
                        semester.stated_total_credits = explicit_total
                        semester.total_credits = explicit_total
                    _append_evidence(semester.evidence, total_evidence)
                continue

            if re.fullmatch(r"teaching\s+scheme\s*:?", line, re.I):
                scheme_lines_remaining = 200
                pending_scheme_field = None
                scheme_page_number = _optional_int(
                    _metadata_value(chunk, "page_number")
                )
                current_section = None
                continue

            if scheme_lines_remaining > 0 and current_course is not None:
                scheme_lines_remaining -= 1
                if pending_scheme_field is not None:
                    field, label = pending_scheme_field
                    if re.fullmatch(rf"(?:{_NUMBER}|[-–—])", line):
                        set_scheme_value(current_course, field, label, line, chunk)
                        pending_scheme_field = None
                        if field == "credits":
                            scheme_lines_remaining = 0
                        continue
                    pending_scheme_field = None

                scheme_label = re.fullmatch(
                    rf"(?P<label>theory|lecture|practical|tutorial|credits?)"
                    rf"\s*:?[ ]*(?P<value>{_NUMBER}|[-–—])?",
                    line,
                    re.I,
                )
                if scheme_label:
                    label = scheme_label.group("label")
                    field = _TEACHING_SCHEME_LABELS[label.lower()]
                    value = scheme_label.group("value")
                    if value is not None:
                        set_scheme_value(current_course, field, label, value, chunk)
                        if field == "credits":
                            scheme_lines_remaining = 0
                    else:
                        pending_scheme_field = (field, label)
                    continue

            header = _table_header(line)
            if header:
                active_header = header
                current_course = None
                current_section = None
                continue

            parsed_course = None
            if active_header:
                parsed_course = _course_from_table_row(
                    line, active_header, current_semester, chunk
                )
            if parsed_course is None:
                parsed_course = _course_from_unheaded_pipe_row(
                    line, current_semester, chunk
                )
            if parsed_course is None:
                parsed_course = _course_from_text_row(line, current_semester, chunk)
            if parsed_course is not None:
                current_course = add_course(parsed_course)
                current_section = None
                continue

            heading = _COURSE_HEADING_PAREN.match(line) or _COURSE_HEADING.match(line)
            if heading:
                code = heading.group("code")
                normalized_code = _normalize_course_code(code)
                if normalized_code is not None:
                    current_course = _find_course_by_code(
                        course_order, normalized_code
                    )
                    if current_course is None:
                        current_course = add_course(
                            Course(
                                course_code=normalized_code,
                                course_title=_clean_line(heading.group("title")),
                                semester=current_semester or chunk_semester,
                                category=_explicit_category(line),
                                evidence=[
                                    _evidence(
                                        chunk,
                                        line,
                                        ["course_code", "course_title"],
                                    )
                                ],
                            )
                        )
                    current_section = None
                    if scheme_page_number != _optional_int(
                        _metadata_value(chunk, "page_number")
                    ):
                        scheme_lines_remaining = 0
                    pending_scheme_field = None
                    continue

            if _is_semantic_stop_heading(line):
                current_section = None
                continue

            if current_course is None:
                continue

            section_match = _section_line(line)
            if section_match:
                current_section, inline_value = section_match
                if inline_value:
                    _add_section_value(
                        current_course,
                        current_section,
                        inline_value,
                        chunk,
                        line,
                    )
                continue

            outcome = re.match(r"^(CO\s*\d+)\s*[:.\-]\s*(.+)$", line, re.I)
            if outcome:
                _add_section_value(
                    current_course,
                    "course_outcomes",
                    line,
                    chunk,
                    line,
                )
                current_section = "course_outcomes"
                continue

            module = re.match(
                r"^(module|unit)\s*(?:[ivx]+|\d+)?\s*[:.\-]?\s*(.+)$",
                line,
                re.I,
            )
            if module:
                _add_section_value(
                    current_course,
                    "modules",
                    line,
                    chunk,
                    line,
                )
                current_section = "modules"
                continue

            if current_section:
                if line.isupper() and len(line.split()) <= 8:
                    current_section = None
                    continue
                _add_section_value(
                    current_course,
                    current_section,
                    line,
                    chunk,
                    line,
                )

    for semester_hint, total, evidence in _columnar_scheme_totals(chunks):
        target_semester = semester_hint
        if target_semester is None and len(semesters) == 1:
            target_semester = next(iter(semesters))
        if target_semester is None:
            continue
        semester = semester_record(target_semester)
        if (
            semester.stated_total_credits is not None
            and semester.stated_total_credits != total
        ):
            warnings.append(
                f"Conflicting stated totals were found for semester {target_semester}."
            )
            continue
        semester.stated_total_credits = total
        semester.total_credits = total
        _append_evidence(semester.evidence, evidence)

    all_courses = list(course_order)
    for semester_number, semester in semesters.items():
        semester_courses = [
            course for course in all_courses if course.semester == semester_number
        ]
        credit_values = [course.credits for course in semester_courses]
        contains_elective_options = any(
            course.category == "University Elective"
            for course in semester_courses
        )
        if (
            semester_courses
            and not contains_elective_options
            and all(value is not None for value in credit_values)
        ):
            semester.calculated_total_credits = sum(
                value for value in credit_values if value is not None
            )
            if semester.total_credits is None:
                semester.total_credits = semester.calculated_total_credits
            for course in semester_courses:
                for item in course.evidence:
                    if "credits" in item.fields or "course_row" in item.fields:
                        _append_evidence(semester.evidence, item)
        if (
            semester.stated_total_credits is not None
            and semester.calculated_total_credits is not None
            and semester.stated_total_credits != semester.calculated_total_credits
        ):
            warnings.append(
                f"Semester {semester_number} stated and calculated credit totals differ."
            )

    semester_list = [semesters[number] for number in sorted(semesters)]
    calculated_total_credits = None
    if semester_list and all(
        semester.total_credits is not None for semester in semester_list
    ):
        calculated_total_credits = sum(
            semester.total_credits
            for semester in semester_list
            if semester.total_credits is not None
        )
        for semester in semester_list:
            for item in semester.evidence:
                _append_evidence(curriculum_evidence, item)
    elif all_courses and all(course.credits is not None for course in all_courses):
        calculated_total_credits = sum(
            course.credits for course in all_courses if course.credits is not None
        )
        for course in all_courses:
            for item in course.evidence:
                _append_evidence(curriculum_evidence, item)

    if (
        stated_total_credits is not None
        and calculated_total_credits is not None
        and stated_total_credits != calculated_total_credits
    ):
        warnings.append(
            "The stated curriculum total differs from the total calculated from extracted data."
        )

    buckets: Dict[str, List[Course]] = {
        "courses": [],
        "professional_electives": [],
        "open_electives": [],
        "projects": [],
        "internships": [],
        "mandatory_courses": [],
    }
    for course in all_courses:
        buckets[_course_bucket(course)].append(course)

    return StructuredCurriculum(
        curriculum_id=str(resolved_curriculum_id),
        document_id=str(resolved_document_id),
        programme=str(programme),
        branch=str(branch),
        year=_optional_int(_single_metadata_value(chunks, "year")),
        version=_single_metadata_value(chunks, "version"),
        total_credits=(
            calculated_total_credits
            if calculated_total_credits is not None
            else stated_total_credits
        ),
        stated_total_credits=stated_total_credits,
        calculated_total_credits=calculated_total_credits,
        semesters=semester_list,
        evidence=curriculum_evidence,
        extraction_warnings=list(dict.fromkeys(warnings)),
        **buckets,
    )
