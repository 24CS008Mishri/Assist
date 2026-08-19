import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from backend.core.auth import AuthenticatedUser, require_authenticated_user
from backend.models.analyzer_schemas import StructuredCurriculum
from backend.services.curriculum_extraction_service import (
    AmbiguousCurriculumError,
    CurriculumNotFoundError,
    InvalidCurriculumMetadataError,
    detect_semester_number,
    extract_structured_curriculum,
)


class FakeCollection:
    def __init__(self, records):
        self.records = records
        self.last_query = None

    def find(self, query, projection):
        self.last_query = query
        return [
            record
            for record in self.records
            if all(record.get(key) == value for key, value in query.items())
        ]


def chunk(text, page_number, chunk_index, **overrides):
    metadata = {
        "source_type": "submitted_curriculum",
        "curriculum_id": "xyz-cse-2026",
        "document_id": "doc_xyz",
        "programme": "B.Tech",
        "branch": "CSE",
        "year": 2026,
        "version": "1.0",
        "owner_id": "designer-a",
        "page_number": page_number,
        "chunk_index": chunk_index,
    }
    metadata.update(overrides)
    return {**metadata, "text": text}


class CurriculumExtractionServiceTests(unittest.TestCase):
    def test_detects_supported_semester_heading_variants(self):
        examples = {
            "Semester I": 1,
            "Semester 1": 1,
            "SEMESTER-II": 2,
            "III Semester": 3,
        }
        for heading, expected in examples.items():
            with self.subTest(heading=heading):
                self.assertEqual(detect_semester_number(heading), expected)

    def test_extracts_tables_totals_special_courses_and_evidence(self):
        records = [
            chunk(
                """SEMESTER-II
Code | Subject | Category | Lecture | Tutorial | Practical | Credit
CS-301 | Data Structures and Algorithms | PCC | 3 | 0 | 4 | 5
PR201 | Mini Project | Project | 0 | 0 | 4 | 2
IN201 | Summer Internship | Internship | 0 | 0 | 4 | 2
MC201 | Environmental Sciences | MC | 2 | 0 | 0 | 0
Total Credits: 9
Grand Total Credits: 17""",
                3,
                2,
            ),
            chunk(
                """Semester I
Course Code | Course Title | Category | L | T | P | Credits
CS101 | Programming for Problem Solving | ESC | 3 | 0 | 2 | 4
MA101 | Engineering Mathematics I | BSC | 3 | 1 | 0 | 4
Total Credits: 8""",
                2,
                1,
            ),
            chunk(
                """Course Code: CS-301 - Data Structures and Algorithms
Prerequisites: Programming Fundamentals
Course Objectives: Understand data organization.
Course Outcomes:
CO1: Implement linear data structures.
Module I: Arrays and linked lists
Assessment: End semester examination and laboratory work.
References: Introduction to Algorithms""",
                4,
                3,
            ),
            chunk(
                "Semester I\nAICTE reference row should never be selected",
                1,
                0,
                source_type="aicte_reference",
            ),
            chunk(
                "Semester VIII\nOTHER101 | Other Curriculum | PCC | 3 | 0 | 0 | 3",
                10,
                99,
                curriculum_id="other-curriculum",
                document_id="doc_other",
            ),
        ]
        collection = FakeCollection(records)

        result = extract_structured_curriculum(
            "xyz-cse-2026", owner_id="designer-a", collection=collection
        )

        self.assertEqual(
            collection.last_query,
            {
                "source_type": "submitted_curriculum",
                "owner_id": "designer-a",
                "curriculum_id": "xyz-cse-2026",
            },
        )
        self.assertEqual([semester.semester_number for semester in result.semesters], [1, 2])
        self.assertEqual(result.semesters[0].total_credits, 8)
        self.assertEqual(result.semesters[1].total_credits, 9)
        self.assertEqual(result.calculated_total_credits, 17)
        self.assertEqual(result.stated_total_credits, 17)
        self.assertEqual(result.total_credits, 17)

        data_structures = next(
            course for course in result.courses if course.course_code == "CS-301"
        )
        self.assertEqual(data_structures.course_title, "Data Structures and Algorithms")
        self.assertEqual(data_structures.semester, 2)
        self.assertEqual(data_structures.category, "PCC")
        self.assertEqual(data_structures.lecture_hours, 3)
        self.assertEqual(data_structures.tutorial_hours, 0)
        self.assertEqual(data_structures.practical_hours, 4)
        self.assertEqual(data_structures.credits, 5)
        self.assertEqual(data_structures.prerequisites, ["Programming Fundamentals"])
        self.assertTrue(data_structures.course_objectives)
        self.assertTrue(data_structures.course_outcomes)
        self.assertTrue(data_structures.modules)
        self.assertTrue(data_structures.assessment_information)
        self.assertTrue(data_structures.references)
        self.assertTrue(
            any(
                evidence.page_number == 3
                and evidence.chunk_index == 2
                and "credits" in evidence.fields
                for evidence in data_structures.evidence
            )
        )

        self.assertEqual([course.course_title for course in result.projects], ["Mini Project"])
        self.assertEqual(
            [course.course_title for course in result.internships],
            ["Summer Internship"],
        )
        self.assertEqual(
            [course.course_title for course in result.mandatory_courses],
            ["Environmental Sciences"],
        )
        self.assertNotIn("Other Curriculum", [course.course_title for course in result.courses])

    def test_extracts_labelled_and_dashed_ltp_rows_and_electives(self):
        collection = FakeCollection(
            [
                chunk(
                    """III Semester
PCC CS-301 Data Structures and Algorithms 3L:0T:4P 5 Credits
PEC PE401 Cloud Computing 3-0-0-3
OEC OE401 Design Thinking 2-0-0-2""",
                    12,
                    30,
                )
            ]
        )

        result = extract_structured_curriculum(
            "xyz-cse-2026", owner_id="designer-a", collection=collection
        )

        course = result.courses[0]
        self.assertEqual(course.course_code, "CS-301")
        self.assertEqual(course.lecture_hours, 3)
        self.assertEqual(course.tutorial_hours, 0)
        self.assertEqual(course.practical_hours, 4)
        self.assertEqual(course.credits, 5)
        self.assertEqual(result.professional_electives[0].course_code, "PE401")
        self.assertEqual(result.open_electives[0].course_code, "OE401")
        self.assertEqual(result.total_credits, 10)

    def test_missing_optional_fields_remain_empty(self):
        collection = FakeCollection(
            [
                chunk(
                    """Semester 1
Course Code | Course Title | L | T | P | Credits
CS101 | Programming Fundamentals | 3 | 0 | 2 | 4""",
                    1,
                    0,
                )
            ]
        )

        result = extract_structured_curriculum(
            "xyz-cse-2026", owner_id="designer-a", collection=collection
        )
        course = result.courses[0]
        self.assertIsNone(course.category)
        self.assertEqual(course.prerequisites, [])
        self.assertEqual(course.course_objectives, [])
        self.assertEqual(course.course_outcomes, [])
        self.assertEqual(course.references, [])

    def test_extracts_column_major_footer_and_vertical_teaching_schemes(self):
        collection = FakeCollection(
            [
                chunk(
                    """Teaching & Examination Scheme for B. Tech Programme
Course
Code
Course Title
Teaching Scheme
CREDIT
TOTAL
TOTAL
HOURS
Examination Scheme
CS501
CS502
DISTRIBUTED SYSTEMS
CLOUD COMPUTING
3.00
2.00
18/50
18.00""",
                    1,
                    0,
                ),
                chunk(
                    """DISTRIBUTED SYSTEMS
CLOUD COMPUTING
3.00
2.00
18/50
18.00
10.00
650""",
                    1,
                    1,
                ),
                chunk(
                    """Teaching & Examination Scheme
Teaching Scheme
CREDIT
TOTAL HOURS
Examination Scheme
100
100
100""",
                    2,
                    2,
                ),
                chunk(
                    """Semester: 5
Distributed Systems (CS501)
Teaching Scheme:
Teaching
Scheme
Hours/Week
Marks
Theory
3
100
Practical
1
50
Tutorial
-
-
Total
5
150
Credit
4
Course Outcomes:
CO1: Explain distributed system principles.
Practical 10: Socket Exercise""",
                    4,
                    10,
                ),
                chunk(
                    """Subject: Cloud Computing (CS502)
Semester: 5
Teaching Scheme:
Theory
2
50
Practical
1
50
Tutorial
-
-
Total
4
100
Credit
3""",
                    5,
                    11,
                ),
                chunk(
                    """Subject:
Semester: 5
Teaching Scheme:
Example University
Network Security (CS503) (University Elective - I)
Course Pre-requisites:
Computer Networks
Theory
2
50
Practical
1
50
Tutorial
-
-
Total
4
100
Credit
3""",
                    6,
                    12,
                ),
            ]
        )

        result = extract_structured_curriculum(
            "xyz-cse-2026", owner_id="designer-a", collection=collection
        )

        courses = result.courses + result.professional_electives
        self.assertEqual(
            [course.course_code for course in courses],
            ["CS501", "CS502", "CS503"],
        )
        self.assertNotIn("PRACTICAL10", [course.course_code for course in courses])

        distributed = courses[0]
        self.assertEqual(distributed.course_title, "Distributed Systems")
        self.assertEqual(distributed.semester, 5)
        self.assertEqual(distributed.lecture_hours, 3)
        self.assertEqual(distributed.tutorial_hours, 0)
        self.assertEqual(distributed.practical_hours, 1)
        self.assertEqual(distributed.credits, 4)
        self.assertTrue(
            any(
                evidence.page_number == 4
                and evidence.chunk_index == 10
                and "credits" in evidence.fields
                for evidence in distributed.evidence
            )
        )

        elective = courses[2]
        self.assertEqual(elective.category, "University Elective")
        self.assertEqual(elective.credits, 3)

        semester = result.semesters[0]
        self.assertEqual(semester.semester_number, 5)
        self.assertEqual(semester.stated_total_credits, 10)
        self.assertEqual(semester.total_credits, 10)
        self.assertIsNone(semester.calculated_total_credits)
        self.assertTrue(
            any(
                evidence.page_number == 1
                and evidence.chunk_index == 1
                and evidence.excerpt == "18.00 10.00 650"
                and "semester_total_credits" in evidence.fields
                for evidence in semester.evidence
            )
        )
        self.assertEqual(result.total_credits, 10)

    def test_semantic_sections_stop_at_real_pdf_boundaries_and_merge_outcomes(self):
        collection = FakeCollection(
            [
                chunk(
                    """Semester: 5
Operating Systems (CS501)
Course Outcomes:
After successful completion, students will be able to:
CO1: Analyze operating-system design trade-offs across
multiple architectures and workloads.
CO2: Evaluate scheduling algorithms using quantitative""",
                    4,
                    20,
                ),
                chunk(
                    """multiple architectures and workloads.
CO2: Evaluate scheduling algorithms using quantitative
performance metrics and justify their use.
Bridge Topics/Self-Study/Revisit:
This bridge material must not become an outcome.
Page 15 of 58
1
Unit
No.""",
                    4,
                    21,
                ),
                chunk(
                    """Machine Learning (CS502)
Pre-requisites online video/ courses:
Linear Algebra
Probability
Self-Study/Further Study components and materials:
Online material that must not become a prerequisite.
Teaching Scheme:
Teaching
Scheme
Hours/Week
Marks
100
50
Total
150
Course Pre-requisites:
Programming Fundamentals
Theory
Course Outcomes:
CO1: Build a valid model.""",
                    5,
                    22,
                ),
                chunk(
                    """Web Engineering (CS503)
Syllabus:
1
2
Unit
No.
Topic
Frontend component architecture
Reactive state management
\x00
Page 20 of 58
Hrs.
Recommended Study Material:
Book content must not become a topic.
Reference Books:
Another book that must not become a topic.
Instructions to Subject Teachers:
Teacher instructions must not become a topic.
Practical List:
Practical content must not become a topic.
Subject:
Unrelated page-header content""",
                    6,
                    23,
                ),
            ]
        )

        result = extract_structured_curriculum(
            "xyz-cse-2026", owner_id="designer-a", collection=collection
        )
        courses = {course.course_code: course for course in result.courses}

        self.assertEqual(
            courses["CS501"].course_outcomes,
            [
                "CO1: Analyze operating-system design trade-offs across "
                "multiple architectures and workloads.",
                "CO2: Evaluate scheduling algorithms using quantitative "
                "performance metrics and justify their use.",
            ],
        )
        self.assertFalse(
            any(
                "Bridge" in outcome or "Page" in outcome
                for outcome in courses["CS501"].course_outcomes
            )
        )

        self.assertEqual(
            courses["CS502"].prerequisites,
            ["Linear Algebra", "Probability", "Programming Fundamentals"],
        )
        self.assertFalse(
            any(
                value in courses["CS502"].prerequisites
                for value in ("Teaching", "Scheme", "Marks", "Total", "Theory")
            )
        )

        self.assertEqual(
            courses["CS503"].topics,
            ["Frontend component architecture", "Reactive state management"],
        )
        flattened_topics = " ".join(courses["CS503"].topics)
        self.assertNotIn("Recommended Study Material", flattened_topics)
        self.assertNotIn("Instructions to Subject Teachers", flattened_topics)
        self.assertNotIn("Practical", flattened_topics)

    def test_nonexistent_or_wrong_source_curriculum_is_not_found(self):
        collection = FakeCollection(
            [
                chunk(
                    "Semester I",
                    1,
                    0,
                    source_type="aicte_reference",
                )
            ]
        )
        with self.assertRaises(CurriculumNotFoundError):
            extract_structured_curriculum(
                "xyz-cse-2026", owner_id="designer-a", collection=collection
            )

    def test_rejects_invalid_or_ambiguous_metadata(self):
        invalid = FakeCollection(
            [chunk("Semester I", 1, 0, branch="ECE")]
        )
        with self.assertRaises(InvalidCurriculumMetadataError):
            extract_structured_curriculum(
                "xyz-cse-2026", owner_id="designer-a", collection=invalid
            )

        ambiguous = FakeCollection(
            [
                chunk("Semester I", 1, 0),
                chunk("Semester II", 2, 1, document_id="doc_second"),
            ]
        )
        with self.assertRaises(AmbiguousCurriculumError):
            extract_structured_curriculum(
                "xyz-cse-2026", owner_id="designer-a", collection=ambiguous
            )

    def test_analyzer_endpoint_returns_result_and_maps_not_found(self):
        client = TestClient(main.app)
        main.app.dependency_overrides[require_authenticated_user] = lambda: (
            AuthenticatedUser(user_id="designer-a", role="designer")
        )
        structured = StructuredCurriculum(
            curriculum_id="xyz-cse-2026",
            document_id="doc_xyz",
            programme="B.Tech",
            branch="CSE",
        )
        try:
            with patch(
                "backend.routers.analyzer.extract_structured_curriculum",
                return_value=structured,
            ):
                response = client.post("/api/analyzer/extract/xyz-cse-2026")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["curriculum_id"], "xyz-cse-2026")

            with patch(
                "backend.routers.analyzer.extract_structured_curriculum",
                side_effect=CurriculumNotFoundError("not found"),
            ):
                missing = client.post("/api/analyzer/extract/missing")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.json(), {"detail": "not found"})
        finally:
            main.app.dependency_overrides.pop(require_authenticated_user, None)


if __name__ == "__main__":
    unittest.main()
