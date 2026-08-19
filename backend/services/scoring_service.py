import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.core.analyzer_criteria import (
    ACTION_VERBS,
    AICTE_BASELINE,
    CATEGORY_FULL_TOLERANCE_RATIO,
    CATEGORY_ZERO_TOLERANCE_RATIO,
    CHECK_DEFINITIONS,
    COMPLIANCE_KEYWORDS,
    CORE_SKILL_IDS,
    CRITERION_LABELS,
    CRITERION_WEIGHTS,
    INDUSTRY_KEYWORDS,
    LOW_EVALUATION_COVERAGE_THRESHOLD,
    MIN_CATEGORY_COVERAGE_RATIO,
    REASONABLE_PRACTICAL_SHARE_RANGE,
    REASONABLE_SEMESTER_CREDIT_RANGE,
    SCORING_VERSION,
    SKILL_TAXONOMY,
    TOTAL_CREDIT_FULL_TOLERANCE,
    TOTAL_CREDIT_ZERO_TOLERANCE,
    CheckDefinition,
)
from backend.models.analyzer_schemas import Course, EvidenceReference, StructuredCurriculum
from backend.models.analyzer_scoring_schemas import (
    AnalyzerScore,
    CheckStatus,
    CriterionScore,
    DocumentScope,
    ScoringCheck,
)


_FULL_PROGRAM_MIN_CREDITS = 120
_FULL_PROGRAM_MAX_CREDITS = 220
_FULL_PROGRAM_CATEGORIES = {"HSMC", "BSC", "ESC", "PCC", "PEC", "OEC"}
_FULL_PROGRAM_CHECK_IDS = {
    "structure.semesters",
    "structure.total_credits",
    "structure.category_distribution",
    "structure.professional_core",
    "structure.professional_elective",
    "structure.open_elective",
    "structure.project_internship",
    "compliance.induction",
    "compliance.environment",
    "compliance.constitution_ikt",
    "compliance.human_values",
    "compliance.mandatory_non_credit",
    "compliance.essential_core",
    *SKILL_TAXONOMY.keys(),
}
_CONDITIONAL_LOCAL_PRESENCE_CHECK_IDS = {
    "compliance.internship",
    "compliance.project",
    "industry.projects",
    "industry.internship",
}
_PROJECT_TITLE = re.compile(r"\b(?:project|capstone)\b", re.I)


@dataclass
class _Evaluation:
    ratio: Optional[float]
    actual: Any = None
    reason: str = ""
    evidence: List[EvidenceReference] = field(default_factory=list)


def _round(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def _all_courses(curriculum: StructuredCurriculum) -> List[Course]:
    return [
        *curriculum.courses,
        *curriculum.professional_electives,
        *curriculum.open_electives,
        *curriculum.projects,
        *curriculum.internships,
        *curriculum.mandatory_courses,
    ]


def _course_text(course: Course) -> str:
    values = [
        course.course_code or "",
        course.course_title,
        course.category or "",
        *course.prerequisites,
        *course.course_objectives,
        *course.course_outcomes,
        *course.modules,
        *course.topics,
        *course.assessment_information,
        *course.references,
    ]
    return " ".join(values).casefold()


def _contains_alias(text: str, aliases: Sequence[str]) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold())
    return any(alias.casefold() in normalized for alias in aliases)


def _unique_evidence(
    sources: Iterable[EvidenceReference], limit: int = 12
) -> List[EvidenceReference]:
    result: List[EvidenceReference] = []
    keys = set()
    for item in sources:
        key = (item.page_number, item.chunk_index, item.excerpt, tuple(item.fields))
        if key not in keys:
            keys.add(key)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _course_evidence(courses: Iterable[Course]) -> List[EvidenceReference]:
    return _unique_evidence(item for course in courses for item in course.evidence)


def _matching_courses(courses: Sequence[Course], aliases: Sequence[str]) -> List[Course]:
    return [course for course in courses if _contains_alias(_course_text(course), aliases)]


def _strong_project_courses(
    curriculum: StructuredCurriculum,
    courses: Sequence[Course],
) -> List[Course]:
    """Use explicit records, categories, or titles rather than syllabus prose."""
    matches: List[Course] = []
    candidates = [
        *curriculum.projects,
        *[
            course
            for course in courses
            if _PROJECT_TITLE.search(course.course_title)
            or "PROJECT" in (course.category or "").strip().upper()
        ],
    ]
    seen = set()
    for course in candidates:
        key = (course.course_code or "", course.course_title.casefold(), course.semester)
        if key not in seen:
            seen.add(key)
            matches.append(course)
    return matches


def _ratio_evaluation(
    ratio: float,
    actual: Any,
    evidence: Iterable[EvidenceReference],
    description: str,
) -> _Evaluation:
    bounded = max(0.0, min(1.0, ratio))
    if bounded >= 1.0:
        reason = f"No marks deducted: {description}."
    elif bounded <= 0.0:
        reason = f"Full deduction: {description}."
    else:
        reason = f"Partial deduction: {description}."
    return _Evaluation(bounded, actual, reason, _unique_evidence(evidence))


def _not_evaluable(reason: str, actual: Any = None) -> _Evaluation:
    return _Evaluation(None, actual, f"Not evaluable: {reason}.")


def _partial_scope_not_evaluable(actual: Any = None) -> _Evaluation:
    return _Evaluation(
        None,
        actual,
        "Not evaluable from a partial curriculum document.",
    )


def _presence(
    present: bool,
    actual: Any,
    evidence: Iterable[EvidenceReference],
    description: str,
) -> _Evaluation:
    return _ratio_evaluation(1.0 if present else 0.0, actual, evidence, description)


def _proximity_ratio(actual: float, expected: float, full: float, zero: float) -> float:
    difference = abs(actual - expected)
    if difference <= full:
        return 1.0
    if difference >= zero:
        return 0.0
    return 1.0 - ((difference - full) / (zero - full))


def _category_proximity(actual: float, expected: float) -> float:
    return _proximity_ratio(
        actual,
        expected,
        expected * CATEGORY_FULL_TOLERANCE_RATIO,
        expected * CATEGORY_ZERO_TOLERANCE_RATIO,
    )


def _category_totals(courses: Sequence[Course]) -> Tuple[Dict[str, float], float, float]:
    totals: Dict[str, float] = {}
    credited = 0.0
    categorized = 0.0
    for course in courses:
        if course.credits is None:
            continue
        credited += course.credits
        category = (course.category or "").strip().upper()
        if category:
            totals[category] = totals.get(category, 0.0) + course.credits
            categorized += course.credits
    return totals, credited, categorized


def _detect_document_scope(
    curriculum: StructuredCurriculum,
    courses: Sequence[Course],
) -> Tuple[DocumentScope, str]:
    semester_numbers = sorted(
        {semester.semester_number for semester in curriculum.semesters}
    )
    semester_set = set(semester_numbers)
    if set(range(1, 9)).issubset(semester_set):
        return (
            DocumentScope.FULL_CURRICULUM,
            "Semesters 1-8 were reliably extracted.",
        )

    spans_programme = (
        len(semester_numbers) >= 7
        and 1 in semester_set
        and 8 in semester_set
        and all(
            semester.total_credits is not None
            for semester in curriculum.semesters
            if semester.semester_number in semester_set
        )
    )
    if spans_programme:
        return (
            DocumentScope.FULL_CURRICULUM,
            "Reliable semester-wise credit structure spans the programme from Semester 1 to Semester 8.",
        )

    programme_total = curriculum.total_credits
    if (
        programme_total is not None
        and _FULL_PROGRAM_MIN_CREDITS
        <= programme_total
        <= _FULL_PROGRAM_MAX_CREDITS
    ):
        return (
            DocumentScope.FULL_CURRICULUM,
            f"A programme-scale total of {programme_total:g} credits was reliably extracted.",
        )

    category_totals, _, _ = _category_totals(courses)
    recognized_categories = {
        category
        for category in category_totals
        if category in _FULL_PROGRAM_CATEGORIES
    }
    recognized_credits = sum(
        category_totals[category] for category in recognized_categories
    )
    if len(recognized_categories) >= 4 and recognized_credits >= _FULL_PROGRAM_MIN_CREDITS:
        return (
            DocumentScope.FULL_CURRICULUM,
            "A programme-scale category-credit distribution was reliably extracted.",
        )

    if len(semester_numbers) == 1:
        return (
            DocumentScope.PARTIAL_CURRICULUM,
            f"Only Semester {semester_numbers[0]} was reliably extracted.",
        )
    if semester_numbers:
        label = ", ".join(str(number) for number in semester_numbers)
        return (
            DocumentScope.PARTIAL_CURRICULUM,
            f"Only Semesters {label} were reliably extracted; complete programme scope was not established.",
        )
    return (
        DocumentScope.PARTIAL_CURRICULUM,
        "No complete Semester 1-8 structure or programme-level credit total was reliably extracted.",
    )


def _apply_scope_constraints(
    evaluations: Dict[str, _Evaluation],
    document_scope: DocumentScope,
) -> None:
    if document_scope != DocumentScope.PARTIAL_CURRICULUM:
        return
    for check_id in _FULL_PROGRAM_CHECK_IDS:
        evaluation = evaluations.get(check_id)
        if evaluation is not None:
            evaluations[check_id] = _partial_scope_not_evaluable(
                evaluation.actual
            )
    for check_id in _CONDITIONAL_LOCAL_PRESENCE_CHECK_IDS:
        evaluation = evaluations.get(check_id)
        if evaluation is not None and (
            evaluation.ratio is None or evaluation.ratio <= 0
        ):
            evaluations[check_id] = _partial_scope_not_evaluable(
                evaluation.actual
            )


def _structure_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    result: Dict[str, _Evaluation] = {}
    semester_count = len({item.semester_number for item in curriculum.semesters})
    if semester_count == 0:
        result["structure.semesters"] = _not_evaluable("no semesters were extracted")
    else:
        difference = abs(semester_count - AICTE_BASELINE["semester_count"])
        ratio = 1.0 if difference == 0 else max(0.0, 1.0 - difference / 4.0)
        result["structure.semesters"] = _ratio_evaluation(
            ratio,
            semester_count,
            (e for semester in curriculum.semesters for e in semester.evidence),
            f"{semester_count} semesters were extracted; expected 8",
        )

    if curriculum.total_credits is None:
        result["structure.total_credits"] = _not_evaluable(
            "no reliable curriculum total was extracted"
        )
    else:
        ratio = _proximity_ratio(
            curriculum.total_credits,
            AICTE_BASELINE["total_credits"],
            TOTAL_CREDIT_FULL_TOLERANCE,
            TOTAL_CREDIT_ZERO_TOLERANCE,
        )
        result["structure.total_credits"] = _ratio_evaluation(
            ratio,
            curriculum.total_credits,
            curriculum.evidence,
            f"total is {curriculum.total_credits:g} credits versus the 163-credit baseline",
        )

    semester_totals = [
        item for item in curriculum.semesters if item.total_credits is not None
    ]
    if not semester_totals:
        result["structure.semester_distribution"] = _not_evaluable(
            "semester credit totals were not extracted"
        )
    else:
        low, high = REASONABLE_SEMESTER_CREDIT_RANGE
        in_range = [item for item in semester_totals if low <= item.total_credits <= high]
        actual = {
            str(item.semester_number): item.total_credits for item in semester_totals
        }
        result["structure.semester_distribution"] = _ratio_evaluation(
            len(in_range) / len(semester_totals),
            actual,
            (e for semester in semester_totals for e in semester.evidence),
            f"{len(in_range)} of {len(semester_totals)} extracted semester totals are in the {low}-{high} range",
        )

    totals, credited, categorized = _category_totals(courses)
    category_coverage = categorized / credited if credited else 0.0
    categories_reliable = credited > 0 and category_coverage >= MIN_CATEGORY_COVERAGE_RATIO
    category_checks = {
        "structure.category_distribution": ("HSMC", "BSC", "ESC"),
        "structure.professional_core": ("PCC",),
        "structure.professional_elective": ("PEC",),
        "structure.open_elective": ("OEC",),
    }
    for check_id, categories in category_checks.items():
        if not categories_reliable:
            result[check_id] = _not_evaluable(
                "category-bearing course credits cover less than 60% of extracted course credits",
                {"categorized_credit_coverage": _round(category_coverage * 100)},
            )
            continue
        ratios = [
            _category_proximity(
                totals.get(category, 0.0),
                AICTE_BASELINE["category_credits"][category],
            )
            for category in categories
        ]
        actual = {category: _round(totals.get(category, 0.0)) for category in categories}
        result[check_id] = _ratio_evaluation(
            sum(ratios) / len(ratios),
            actual,
            _course_evidence(
                [course for course in courses if (course.category or "").upper() in categories]
            ),
            f"extracted category credits are {actual}",
        )

    project_courses = [*curriculum.projects, *curriculum.internships]
    project_credits = [course.credits for course in project_courses if course.credits is not None]
    if not project_courses or not project_credits:
        result["structure.project_internship"] = _not_evaluable(
            "project/internship credits were not reliably extracted"
        )
    else:
        actual = sum(project_credits)
        expected = AICTE_BASELINE["category_credits"]["PROJECT_INTERNSHIP"]
        result["structure.project_internship"] = _ratio_evaluation(
            _category_proximity(actual, expected),
            _round(actual),
            _course_evidence(project_courses),
            f"project/internship total is {actual:g} credits versus the {expected}-credit baseline",
        )

    ltp_courses = [
        course
        for course in courses
        if any(
            value is not None
            for value in (course.lecture_hours, course.tutorial_hours, course.practical_hours)
        )
    ]
    if not ltp_courses:
        result["structure.ltp_balance"] = _not_evaluable("no L-T-P values were extracted")
    else:
        total_hours = sum(
            (course.lecture_hours or 0)
            + (course.tutorial_hours or 0)
            + (course.practical_hours or 0)
            for course in ltp_courses
        )
        practical = sum(course.practical_hours or 0 for course in ltp_courses)
        if total_hours <= 0:
            result["structure.ltp_balance"] = _not_evaluable(
                "extracted L-T-P values contain no positive hours"
            )
        else:
            share = practical / total_hours
            low, high = REASONABLE_PRACTICAL_SHARE_RANGE
            if low <= share <= high:
                ratio = 1.0
            else:
                distance = low - share if share < low else share - high
                ratio = max(0.0, 1.0 - distance / 0.20)
            result["structure.ltp_balance"] = _ratio_evaluation(
                ratio,
                {"practical_share_percent": _round(share * 100)},
                _course_evidence(ltp_courses),
                f"practical hours are {_round(share * 100)}% of extracted L-T-P hours",
            )
    return result


def _keyword_presence_evaluations(
    courses: Sequence[Course],
    keyword_map: Dict[str, Tuple[str, ...]],
) -> Dict[str, _Evaluation]:
    if not courses:
        return {
            check_id: _not_evaluable("no courses were extracted")
            for check_id in keyword_map
        }
    result = {}
    for check_id, aliases in keyword_map.items():
        matches = _matching_courses(courses, aliases)
        result[check_id] = _presence(
            bool(matches),
            [course.course_title for course in matches],
            _course_evidence(matches),
            f"matched {len(matches)} course(s) using the configured aliases",
        )
    return result


def _compliance_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    result = _keyword_presence_evaluations(courses, COMPLIANCE_KEYWORDS)
    if not courses:
        for check_id in (
            "compliance.mandatory_non_credit",
            "compliance.internship",
            "compliance.project",
            "compliance.essential_core",
        ):
            result[check_id] = _not_evaluable("no courses were extracted")
        return result

    internship_matches = list(curriculum.internships) or _matching_courses(
        courses, ("internship", "industrial training", "industry training")
    )
    project_matches = _strong_project_courses(curriculum, courses)
    result["compliance.internship"] = _presence(
        bool(internship_matches),
        [course.course_title for course in internship_matches],
        _course_evidence(internship_matches),
        f"matched {len(internship_matches)} internship/industrial-exposure course(s)",
    )
    result["compliance.project"] = _presence(
        bool(project_matches),
        [course.course_title for course in project_matches],
        _course_evidence(project_matches),
        f"matched {len(project_matches)} project/seminar course(s)",
    )
    mandatory = list(curriculum.mandatory_courses) or [
        course for course in courses if (course.category or "").upper() == "MC"
    ]
    if not mandatory:
        result["compliance.mandatory_non_credit"] = _not_evaluable(
            "no mandatory-course records were reliably extracted"
        )
    else:
        known_credits = [course for course in mandatory if course.credits is not None]
        if not known_credits:
            result["compliance.mandatory_non_credit"] = _not_evaluable(
                "mandatory courses were extracted without reliable credit values",
                [course.course_title for course in mandatory],
            )
        else:
            zero_credit = [course for course in known_credits if course.credits == 0]
            result["compliance.mandatory_non_credit"] = _ratio_evaluation(
                len(zero_credit) / len(known_credits),
                {
                    "zero_credit_courses": len(zero_credit),
                    "mandatory_courses_with_credit_data": len(known_credits),
                },
                _course_evidence(known_credits),
                f"{len(zero_credit)} of {len(known_credits)} mandatory courses with credit data carry zero credit",
            )
    matched: Dict[str, List[str]] = {}
    core_evidence: List[EvidenceReference] = []
    for skill_id in CORE_SKILL_IDS:
        skill_courses = _matching_courses(courses, SKILL_TAXONOMY[skill_id])
        if skill_courses:
            matched[skill_id] = [course.course_title for course in skill_courses]
            core_evidence.extend(_course_evidence(skill_courses))
    result["compliance.essential_core"] = _ratio_evaluation(
        len(matched) / len(CORE_SKILL_IDS),
        {"matched": matched, "matched_count": len(matched), "expected_count": len(CORE_SKILL_IDS)},
        core_evidence,
        f"{len(matched)} of {len(CORE_SKILL_IDS)} configured essential core skill groups were matched",
    )
    return result


def _industry_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    result = _keyword_presence_evaluations(
        courses,
        {
            key: aliases
            for key, aliases in INDUSTRY_KEYWORDS.items()
            if key not in {"industry.practical_programming", "industry.emerging_electives"}
        },
    )
    if not courses:
        for check_id in (
            "industry.practical_programming",
            "industry.projects",
            "industry.internship",
            "industry.emerging_electives",
        ):
            result[check_id] = _not_evaluable("no courses were extracted")
        return result

    programming = _matching_courses(courses, INDUSTRY_KEYWORDS["industry.practical_programming"])
    if not programming:
        result["industry.practical_programming"] = _presence(
            False, [], [], "no programming course/topic aliases were matched"
        )
    elif all(course.practical_hours is None for course in programming):
        result["industry.practical_programming"] = _not_evaluable(
            "programming was detected but its practical-hour data was not extracted",
            [course.course_title for course in programming],
        )
    else:
        practical = [course for course in programming if (course.practical_hours or 0) > 0]
        result["industry.practical_programming"] = _presence(
            bool(practical),
            [course.course_title for course in practical],
            _course_evidence(programming),
            f"{len(practical)} matched programming course(s) have positive practical hours",
        )

    projects = _strong_project_courses(curriculum, courses)
    internships = list(curriculum.internships) or _matching_courses(
        courses, ("internship", "industrial training", "industry training")
    )
    result["industry.projects"] = _presence(
        bool(projects), [c.course_title for c in projects], _course_evidence(projects),
        f"matched {len(projects)} project course(s)",
    )
    result["industry.internship"] = _presence(
        bool(internships), [c.course_title for c in internships], _course_evidence(internships),
        f"matched {len(internships)} internship course(s)",
    )

    electives = [*curriculum.professional_electives, *curriculum.open_electives]
    if not electives:
        result["industry.emerging_electives"] = _not_evaluable(
            "no professional/open electives were extracted"
        )
    else:
        matches = _matching_courses(electives, INDUSTRY_KEYWORDS["industry.emerging_electives"])
        result["industry.emerging_electives"] = _presence(
            bool(matches), [c.course_title for c in matches], _course_evidence(matches),
            f"matched {len(matches)} emerging-area elective(s)",
        )
    return result


def _learning_outcome_evaluations(courses: Sequence[Course]) -> Dict[str, _Evaluation]:
    check_ids = (
        "outcomes.course_coverage",
        "outcomes.objective_coverage",
        "outcomes.density",
        "outcomes.action_verbs",
        "outcomes.core_course_coverage",
    )
    if not courses:
        return {check_id: _not_evaluable("no courses were extracted") for check_id in check_ids}

    outcome_courses = [course for course in courses if course.course_outcomes]
    objective_courses = [course for course in courses if course.course_objectives]
    result: Dict[str, _Evaluation] = {}
    if not outcome_courses:
        for check_id in (
            "outcomes.course_coverage",
            "outcomes.density",
            "outcomes.action_verbs",
            "outcomes.core_course_coverage",
        ):
            result[check_id] = _not_evaluable(
                "no course outcomes were extracted; absence cannot be distinguished from extraction failure"
            )
    else:
        coverage = len(outcome_courses) / len(courses)
        result["outcomes.course_coverage"] = _ratio_evaluation(
            min(1.0, coverage / 0.90),
            {"documented_courses": len(outcome_courses), "total_courses": len(courses)},
            _course_evidence(outcome_courses),
            f"{len(outcome_courses)} of {len(courses)} courses have extracted outcomes",
        )
        density = sum(min(len(course.course_outcomes) / 4.0, 1.0) for course in outcome_courses) / len(outcome_courses)
        result["outcomes.density"] = _ratio_evaluation(
            density,
            {"average_outcomes_per_documented_course": _round(sum(len(c.course_outcomes) for c in outcome_courses) / len(outcome_courses))},
            _course_evidence(outcome_courses),
            "documented courses were compared with the four-outcome analyzer target",
        )
        outcomes = [value for course in outcome_courses for value in course.course_outcomes]
        action_pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(verb) + r"(?:s|d|ed|ing)?" for verb in ACTION_VERBS) + r")\b",
            re.I,
        )
        action_count = sum(bool(action_pattern.search(value)) for value in outcomes)
        action_ratio = action_count / len(outcomes)
        result["outcomes.action_verbs"] = _ratio_evaluation(
            min(1.0, action_ratio / 0.80),
            {"action_oriented": action_count, "total_outcomes": len(outcomes)},
            _course_evidence(outcome_courses),
            f"{action_count} of {len(outcomes)} outcomes contain a configured action verb",
        )
        core_courses = [
            course
            for course in courses
            if any(_contains_alias(_course_text(course), SKILL_TAXONOMY[skill]) for skill in CORE_SKILL_IDS)
        ]
        if not core_courses:
            result["outcomes.core_course_coverage"] = _not_evaluable(
                "no core courses could be identified by the configured aliases"
            )
        else:
            documented = [course for course in core_courses if course.course_outcomes]
            ratio = len(documented) / len(core_courses)
            result["outcomes.core_course_coverage"] = _ratio_evaluation(
                min(1.0, ratio / 0.90),
                {"documented_core_courses": len(documented), "detected_core_courses": len(core_courses)},
                _course_evidence(core_courses),
                f"{len(documented)} of {len(core_courses)} detected core courses have outcomes",
            )

    if not objective_courses:
        result["outcomes.objective_coverage"] = _not_evaluable(
            "no course objectives were extracted; absence cannot be distinguished from extraction failure"
        )
    else:
        coverage = len(objective_courses) / len(courses)
        result["outcomes.objective_coverage"] = _ratio_evaluation(
            min(1.0, coverage / 0.90),
            {"documented_courses": len(objective_courses), "total_courses": len(courses)},
            _course_evidence(objective_courses),
            f"{len(objective_courses)} of {len(courses)} courses have extracted objectives",
        )
    return result


def _assessment_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    check_ids = (
        "assessment.course_coverage",
        "assessment.theory_practical",
        "assessment.project_evaluation",
        "assessment.internship_evaluation",
        "assessment.practical_alignment",
    )
    if not courses:
        return {check_id: _not_evaluable("no courses were extracted") for check_id in check_ids}
    assessed = [course for course in courses if course.assessment_information]
    if not assessed:
        return {
            check_id: _not_evaluable(
                "no assessment information was extracted; absence cannot be distinguished from extraction failure"
            )
            for check_id in check_ids
        }
    result: Dict[str, _Evaluation] = {}
    coverage = len(assessed) / len(courses)
    result["assessment.course_coverage"] = _ratio_evaluation(
        min(1.0, coverage / 0.90),
        {"documented_courses": len(assessed), "total_courses": len(courses)},
        _course_evidence(assessed),
        f"{len(assessed)} of {len(courses)} courses have assessment information",
    )
    assessment_text = " ".join(value for course in assessed for value in course.assessment_information)
    has_theory = _contains_alias(assessment_text, ("exam", "written", "theory", "quiz"))
    has_practical = _contains_alias(assessment_text, ("practical", "laboratory", "lab", "viva", "project"))
    result["assessment.theory_practical"] = _ratio_evaluation(
        (int(has_theory) + int(has_practical)) / 2,
        {"theory": has_theory, "practical": has_practical},
        _course_evidence(assessed),
        f"theory assessment detected={has_theory}; practical assessment detected={has_practical}",
    )
    for check_id, specialized in (
        ("assessment.project_evaluation", curriculum.projects),
        ("assessment.internship_evaluation", curriculum.internships),
    ):
        if not specialized:
            result[check_id] = _not_evaluable(
                f"no {'project' if 'project' in check_id else 'internship'} courses were extracted"
            )
        else:
            documented = [course for course in specialized if course.assessment_information]
            result[check_id] = _ratio_evaluation(
                len(documented) / len(specialized),
                {"documented_courses": len(documented), "total_courses": len(specialized)},
                _course_evidence(specialized),
                f"{len(documented)} of {len(specialized)} relevant courses have assessment information",
            )
    practical_courses = [course for course in courses if (course.practical_hours or 0) > 0]
    if not practical_courses:
        result["assessment.practical_alignment"] = _not_evaluable(
            "no courses with positive practical hours were extracted"
        )
    else:
        aligned = [
            course
            for course in practical_courses
            if _contains_alias(
                " ".join(course.assessment_information),
                ("practical", "laboratory", "lab", "viva", "project", "continuous"),
            )
        ]
        result["assessment.practical_alignment"] = _ratio_evaluation(
            len(aligned) / len(practical_courses),
            {"aligned_courses": len(aligned), "practical_courses": len(practical_courses)},
            _course_evidence(practical_courses),
            f"{len(aligned)} of {len(practical_courses)} practical courses have practical-assessment wording",
        )
    return result


def _resource_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    check_ids = (
        "resources.reference_coverage",
        "resources.labs_practicals",
        "resources.online_learning",
        "resources.experimental",
        "resources.project_lab",
    )
    if not courses:
        return {check_id: _not_evaluable("no courses were extracted") for check_id in check_ids}
    result: Dict[str, _Evaluation] = {}
    referenced = [course for course in courses if course.references]
    if not referenced:
        result["resources.reference_coverage"] = _not_evaluable(
            "no references were extracted; absence cannot be distinguished from extraction failure"
        )
        result["resources.online_learning"] = _not_evaluable(
            "no reference fields were extracted"
        )
    else:
        coverage = len(referenced) / len(courses)
        result["resources.reference_coverage"] = _ratio_evaluation(
            min(1.0, coverage / 0.80),
            {"courses_with_references": len(referenced), "total_courses": len(courses)},
            _course_evidence(referenced),
            f"{len(referenced)} of {len(courses)} courses have extracted references",
        )
        online = [
            course
            for course in referenced
            if _contains_alias(" ".join(course.references), ("nptel", "swayam", "mooc", "coursera", "edx"))
        ]
        result["resources.online_learning"] = _presence(
            bool(online), [course.course_title for course in online], _course_evidence(online),
            f"matched online-learning references in {len(online)} course(s)",
        )

    explicit_ltp = [course for course in courses if course.practical_hours is not None]
    lab_courses = [
        course
        for course in courses
        if (course.practical_hours or 0) > 0
        or _contains_alias(_course_text(course), ("laboratory", " lab", "practical"))
    ]
    if not explicit_ltp and not lab_courses:
        result["resources.labs_practicals"] = _not_evaluable(
            "no practical-hour or explicit laboratory data was extracted"
        )
        result["resources.experimental"] = _not_evaluable(
            "no L-T-P practical-hour data was extracted"
        )
    else:
        lab_ratio = min(1.0, (len(lab_courses) / len(courses)) / 0.25)
        result["resources.labs_practicals"] = _ratio_evaluation(
            lab_ratio,
            {"lab_or_practical_courses": len(lab_courses), "total_courses": len(courses)},
            _course_evidence(lab_courses),
            f"{len(lab_courses)} of {len(courses)} courses have practical/lab evidence",
        )
        positive_practical = [course for course in explicit_ltp if (course.practical_hours or 0) > 0]
        result["resources.experimental"] = _ratio_evaluation(
            len(positive_practical) / len(explicit_ltp) if explicit_ltp else 0.0,
            {"positive_practical_courses": len(positive_practical), "courses_with_practical_data": len(explicit_ltp)},
            _course_evidence(explicit_ltp),
            f"{len(positive_practical)} of {len(explicit_ltp)} courses with practical data have positive hours",
        )

    relevant = [*curriculum.projects, *lab_courses]
    if not relevant:
        result["resources.project_lab"] = _not_evaluable(
            "no project or lab courses were extracted"
        )
    else:
        semantic = [course for course in relevant if course.references or course.topics or course.modules]
        if not semantic:
            result["resources.project_lab"] = _not_evaluable(
                "project/lab courses lack extractable resource-bearing fields"
            )
        else:
            resource_courses = [
                course
                for course in semantic
                if _contains_alias(
                    " ".join([*course.references, *course.topics, *course.modules]),
                    ("equipment", "software", "tool", "platform", "dataset", "laboratory", "resource"),
                )
            ]
            result["resources.project_lab"] = _ratio_evaluation(
                len(resource_courses) / len(semantic),
                {"courses_with_resource_evidence": len(resource_courses), "evaluable_project_lab_courses": len(semantic)},
                _course_evidence(semantic),
                f"{len(resource_courses)} of {len(semantic)} evaluable project/lab courses name resources",
            )
    return result


def _skill_evaluations(
    curriculum: StructuredCurriculum, courses: Sequence[Course]
) -> Dict[str, _Evaluation]:
    if not courses:
        return {
            check_id: _not_evaluable("no courses were extracted")
            for check_id in SKILL_TAXONOMY
        }
    result = _keyword_presence_evaluations(courses, SKILL_TAXONOMY)
    practical = [course for course in courses if (course.practical_hours or 0) > 0]
    applied = [*curriculum.projects, *curriculum.internships, *practical]
    if applied:
        result["skills.projects_practical"] = _presence(
            True,
            [course.course_title for course in applied],
            _course_evidence(applied),
            f"matched {len(applied)} project, internship, or practical course record(s)",
        )
    return result


def _build_check(definition: CheckDefinition, evaluation: _Evaluation) -> ScoringCheck:
    if evaluation.ratio is None:
        status = CheckStatus.NOT_EVALUABLE
        obtained = None
    else:
        ratio = max(0.0, min(1.0, evaluation.ratio))
        obtained = _round(definition.maximum_marks * ratio)
        if ratio >= 1.0:
            status = CheckStatus.PASS
        elif ratio <= 0.0:
            status = CheckStatus.FAIL
        else:
            status = CheckStatus.PARTIAL
    return ScoringCheck(
        check_id=definition.check_id,
        criterion=definition.criterion,
        title=definition.title,
        rule_type=definition.rule_type,
        status=status,
        obtained_marks=obtained,
        maximum_marks=definition.maximum_marks,
        expected=definition.expected,
        actual=evaluation.actual,
        deduction_reason=evaluation.reason,
        curriculum_evidence=evaluation.evidence,
    )


def score_structured_curriculum(curriculum: StructuredCurriculum) -> AnalyzerScore:
    """Score a Phase 2 curriculum deterministically without database writes or LLM calls."""
    courses = _all_courses(curriculum)
    document_scope, scope_reason = _detect_document_scope(curriculum, courses)
    evaluations: Dict[str, _Evaluation] = {}
    evaluations.update(_structure_evaluations(curriculum, courses))
    evaluations.update(_compliance_evaluations(curriculum, courses))
    evaluations.update(_industry_evaluations(curriculum, courses))
    evaluations.update(_learning_outcome_evaluations(courses))
    evaluations.update(_assessment_evaluations(curriculum, courses))
    evaluations.update(_resource_evaluations(curriculum, courses))
    evaluations.update(_skill_evaluations(curriculum, courses))
    _apply_scope_constraints(evaluations, document_scope)

    criteria: List[CriterionScore] = []
    for criterion, weight in CRITERION_WEIGHTS.items():
        checks = [
            _build_check(definition, evaluations[definition.check_id])
            for definition in CHECK_DEFINITIONS
            if definition.criterion == criterion
        ]
        evaluable = [check for check in checks if check.obtained_marks is not None]
        obtained = sum(check.obtained_marks or 0.0 for check in evaluable)
        maximum = sum(check.maximum_marks for check in evaluable)
        score = _round(obtained / maximum * 100) if maximum else None
        configured_maximum = sum(check.maximum_marks for check in checks)
        coverage = _round(maximum / configured_maximum * 100) if configured_maximum else 0.0
        criteria.append(
            CriterionScore(
                criterion=criterion,
                label=CRITERION_LABELS[criterion],
                score=score,
                weight=weight,
                obtained_marks=_round(obtained),
                evaluable_maximum_marks=_round(maximum),
                configured_maximum_marks=_round(configured_maximum),
                evaluation_coverage=coverage,
                low_coverage=coverage < LOW_EVALUATION_COVERAGE_THRESHOLD,
                checks=checks,
            )
        )

    evaluable_criteria = [criterion for criterion in criteria if criterion.score is not None]
    evaluable_weight = sum(criterion.weight for criterion in evaluable_criteria)
    total_weight = sum(criterion.weight for criterion in criteria)
    overall_coverage = (
        _round(
            sum(criterion.evaluation_coverage * criterion.weight for criterion in criteria)
            / total_weight
        )
        if total_weight
        else 0.0
    )
    overall = (
        _round(
            sum(criterion.score * criterion.weight for criterion in evaluable_criteria)
            / evaluable_weight
        )
        if evaluable_weight
        else None
    )
    return AnalyzerScore(
        curriculum_id=curriculum.curriculum_id,
        document_id=curriculum.document_id,
        scoring_version=SCORING_VERSION,
        document_scope=document_scope,
        scope_reason=scope_reason,
        overall_score=overall,
        evaluable_weight=_round(evaluable_weight),
        overall_evaluation_coverage=overall_coverage,
        low_coverage=overall_coverage < LOW_EVALUATION_COVERAGE_THRESHOLD,
        criteria=criteria,
    )
