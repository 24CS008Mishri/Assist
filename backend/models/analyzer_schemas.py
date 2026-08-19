from typing import List, Optional

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    excerpt: str
    fields: List[str] = Field(default_factory=list)


class Semester(BaseModel):
    semester_number: int
    total_credits: Optional[float] = None
    stated_total_credits: Optional[float] = None
    calculated_total_credits: Optional[float] = None
    evidence: List[EvidenceReference] = Field(default_factory=list)


class Course(BaseModel):
    course_code: Optional[str] = None
    course_title: str
    semester: Optional[int] = None
    category: Optional[str] = None
    lecture_hours: Optional[float] = None
    tutorial_hours: Optional[float] = None
    practical_hours: Optional[float] = None
    credits: Optional[float] = None
    prerequisites: List[str] = Field(default_factory=list)
    course_objectives: List[str] = Field(default_factory=list)
    course_outcomes: List[str] = Field(default_factory=list)
    modules: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    assessment_information: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    evidence: List[EvidenceReference] = Field(default_factory=list)


class StructuredCurriculum(BaseModel):
    curriculum_id: str
    document_id: str
    programme: str
    branch: str
    year: Optional[int] = None
    version: Optional[str] = None
    total_credits: Optional[float] = None
    stated_total_credits: Optional[float] = None
    calculated_total_credits: Optional[float] = None
    semesters: List[Semester] = Field(default_factory=list)
    courses: List[Course] = Field(default_factory=list)
    professional_electives: List[Course] = Field(default_factory=list)
    open_electives: List[Course] = Field(default_factory=list)
    projects: List[Course] = Field(default_factory=list)
    internships: List[Course] = Field(default_factory=list)
    mandatory_courses: List[Course] = Field(default_factory=list)
    evidence: List[EvidenceReference] = Field(default_factory=list)
    extraction_warnings: List[str] = Field(default_factory=list)
