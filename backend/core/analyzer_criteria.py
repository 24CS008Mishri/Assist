from dataclasses import dataclass
from typing import Any, Dict, Tuple


SCORING_VERSION = "cse_v1"

AICTE_MANDATORY = "AICTE_MANDATORY"
AICTE_MODEL_REFERENCE = "AICTE_MODEL_REFERENCE"
ANALYZER_DERIVED = "ANALYZER_DERIVED"

# Until an official excerpt clearly establishes a binding requirement, the
# existing Phase 3 AICTE checks are model-curriculum comparisons, not mandates.
AICTE_EXPLICIT = AICTE_MODEL_REFERENCE
LOW_EVALUATION_COVERAGE_THRESHOLD = 50.0

# These are analyzer scoring weights, not AICTE-prescribed percentages.
CRITERION_WEIGHTS: Dict[str, int] = {
    "structure": 20,
    "compliance": 15,
    "industry_relevance": 15,
    "learning_outcomes": 15,
    "assessment": 10,
    "resources": 10,
    "skill_coverage": 15,
}

CRITERION_LABELS: Dict[str, str] = {
    "structure": "Structure",
    "compliance": "Compliance",
    "industry_relevance": "Industry Relevance",
    "learning_outcomes": "Learning Outcomes",
    "assessment": "Assessment",
    "resources": "Resources",
    "skill_coverage": "Skill Coverage",
}

AICTE_REFERENCE = (
    "AICTE B.Tech CSE model-curriculum baseline supplied for analyzer version cse_v1. "
    "Model values are comparison references and are not automatically regulatory minima."
)

AICTE_BASELINE: Dict[str, Any] = {
    "total_credits": 163,
    "semester_count": 8,
    "category_credits": {
        "HSMC": 16,
        "BSC": 23,
        "ESC": 29,
        "PCC": 59,
        "PEC": 12,
        "OEC": 9,
        "PROJECT_INTERNSHIP": 15,
    },
}

# A difference of up to three credits is treated as normal model variation.
TOTAL_CREDIT_FULL_TOLERANCE = 3
TOTAL_CREDIT_ZERO_TOLERANCE = 25
CATEGORY_FULL_TOLERANCE_RATIO = 0.10
CATEGORY_ZERO_TOLERANCE_RATIO = 0.50
MIN_CATEGORY_COVERAGE_RATIO = 0.60
REASONABLE_SEMESTER_CREDIT_RANGE = (15, 26)
REASONABLE_PRACTICAL_SHARE_RANGE = (0.20, 0.45)


@dataclass(frozen=True)
class CheckDefinition:
    check_id: str
    criterion: str
    title: str
    maximum_marks: int
    rule_type: str
    expected: Any
    baseline_note: str


def _check(
    check_id: str,
    criterion: str,
    title: str,
    maximum_marks: int,
    rule_type: str,
    expected: Any,
    baseline_note: str,
) -> CheckDefinition:
    return CheckDefinition(
        check_id=check_id,
        criterion=criterion,
        title=title,
        maximum_marks=maximum_marks,
        rule_type=rule_type,
        expected=expected,
        baseline_note=baseline_note,
    )


CHECK_DEFINITIONS: Tuple[CheckDefinition, ...] = (
    # Structure: 100 marks
    _check("structure.semesters", "structure", "Eight-semester structure", 10, AICTE_EXPLICIT, 8, "The AICTE B.Tech model curriculum uses eight semesters."),
    _check("structure.total_credits", "structure", "Total curriculum credits", 15, AICTE_EXPLICIT, 163, "The supplied AICTE CSE model baseline totals 163 credits; minor variation is tolerated."),
    _check("structure.semester_distribution", "structure", "Semester credit distribution", 10, ANALYZER_DERIVED, "15-26 credits per semester", "Analyzer-derived workload consistency range; it is not an AICTE-prescribed percentage."),
    _check("structure.category_distribution", "structure", "HSMC/BSC/ESC distribution", 15, AICTE_EXPLICIT, {"HSMC": 16, "BSC": 23, "ESC": 29}, "AICTE model category values: HSMC 16, BSC 23, and ESC 29 credits."),
    _check("structure.professional_core", "structure", "Professional Core credits", 15, AICTE_EXPLICIT, 59, "The supplied AICTE CSE model baseline contains 59 Professional Core credits."),
    _check("structure.professional_elective", "structure", "Professional Elective credits", 10, AICTE_EXPLICIT, 12, "The supplied AICTE CSE model baseline contains 12 Professional Elective credits."),
    _check("structure.open_elective", "structure", "Open Elective credits", 10, AICTE_EXPLICIT, 9, "The supplied AICTE CSE model baseline contains 9 Open Elective credits."),
    _check("structure.project_internship", "structure", "Project/seminar/internship credits", 10, AICTE_EXPLICIT, 15, "The supplied AICTE CSE model baseline assigns 15 credits to project, seminar, and internship components."),
    _check("structure.ltp_balance", "structure", "Lecture-tutorial-practical balance", 5, ANALYZER_DERIVED, "20%-45% practical share", "Analyzer-derived practical exposure range; it is not a regulatory threshold."),
    # Compliance: 100 marks
    _check("compliance.induction", "compliance", "Induction programme", 10, AICTE_EXPLICIT, "Induction programme present", "The AICTE model structure includes an induction programme component."),
    _check("compliance.environment", "compliance", "Environmental Sciences", 10, AICTE_EXPLICIT, "Environmental Sciences present", "Environmental Sciences is an identifiable model-curriculum component."),
    _check("compliance.constitution_ikt", "compliance", "Constitution/Indian knowledge component", 10, AICTE_EXPLICIT, "Constitution of India or Indian Knowledge Tradition present", "The model/reference set contains Constitution/Indian-knowledge components where applicable."),
    _check("compliance.human_values", "compliance", "Universal Human Values", 10, AICTE_EXPLICIT, "Universal Human Values present", "Universal Human Values is an identifiable model-curriculum component."),
    _check("compliance.mandatory_non_credit", "compliance", "Mandatory non-credit components", 5, AICTE_EXPLICIT, "Extracted mandatory components carry zero credit", "The supplied AICTE model structure includes mandatory non-credit components."),
    _check("compliance.internship", "compliance", "Internship/industrial exposure", 15, AICTE_EXPLICIT, "Internship or industrial exposure present", "The AICTE model includes internship/industrial exposure; this check compares model coverage, not legal compliance."),
    _check("compliance.project", "compliance", "Project component", 15, AICTE_EXPLICIT, "Project component present", "The AICTE model includes a project component; this check compares model coverage."),
    _check("compliance.essential_core", "compliance", "Essential CSE core-area coverage", 25, AICTE_EXPLICIT, "All listed AICTE CSE core areas represented", "Core areas supplied for cse_v1 include programming, DSA, discrete mathematics, architecture, OS, algorithms, databases, ML, networks, cyber security, theory of computation, and compiler design."),
    # Industry relevance: 100 marks
    _check("industry.machine_learning", "industry_relevance", "Machine Learning/Data exposure", 15, ANALYZER_DERIVED, "Relevant course/topic present", "Analyzer-derived industry signal based on normalized titles and topics."),
    _check("industry.cyber_security", "industry_relevance", "Cyber Security exposure", 15, ANALYZER_DERIVED, "Relevant course/topic present", "Analyzer-derived industry signal based on normalized titles and topics."),
    _check("industry.cloud_distributed", "industry_relevance", "Cloud/distributed systems exposure", 15, ANALYZER_DERIVED, "Relevant course/topic present", "Analyzer-derived modern systems signal."),
    _check("industry.practical_programming", "industry_relevance", "Practical programming", 15, ANALYZER_DERIVED, "Programming course with practical component", "Analyzer-derived practical programming signal from titles/topics and L-T-P values."),
    _check("industry.projects", "industry_relevance", "Project-based learning", 15, ANALYZER_DERIVED, "Project present", "Analyzer-derived applied-learning signal."),
    _check("industry.internship", "industry_relevance", "Internship/industry exposure", 10, ANALYZER_DERIVED, "Internship present", "Analyzer-derived industry-exposure signal."),
    _check("industry.emerging_electives", "industry_relevance", "Modern/emerging electives", 15, ANALYZER_DERIVED, "At least one emerging elective", "Analyzer-derived signal for elective exposure to current CSE areas."),
    # Learning outcomes: 100 marks
    _check("outcomes.course_coverage", "learning_outcomes", "Courses with stated outcomes", 35, ANALYZER_DERIVED, "Outcomes for at least 90% of courses", "Analyzer scoring weight based on extractable outcome coverage; not an AICTE percentage."),
    _check("outcomes.objective_coverage", "learning_outcomes", "Courses with stated objectives", 20, ANALYZER_DERIVED, "Objectives for at least 90% of courses", "Analyzer scoring weight based on extractable objective coverage."),
    _check("outcomes.density", "learning_outcomes", "Outcome coverage density", 15, ANALYZER_DERIVED, "At least 4 outcomes per documented course", "Analyzer-derived structural density target; no semantic quality claim is made."),
    _check("outcomes.action_verbs", "learning_outcomes", "Action-oriented outcome wording", 15, ANALYZER_DERIVED, "At least 80% of outcomes contain a recognized action verb", "Deterministic verb-presence check; this is not deep Bloom's-taxonomy analysis."),
    _check("outcomes.core_course_coverage", "learning_outcomes", "Core courses with outcomes", 15, ANALYZER_DERIVED, "Outcomes present for at least 90% of detected core courses", "Analyzer-derived completeness check for detected major CSE core courses."),
    # Assessment: 100 marks
    _check("assessment.course_coverage", "assessment", "Courses with assessment information", 35, ANALYZER_DERIVED, "Assessment information for at least 90% of courses", "Analyzer-derived documentation completeness check."),
    _check("assessment.theory_practical", "assessment", "Theory and practical assessment", 20, ANALYZER_DERIVED, "Both theory and practical assessment represented", "Deterministic keyword check over extracted assessment descriptions."),
    _check("assessment.project_evaluation", "assessment", "Project evaluation", 20, ANALYZER_DERIVED, "Evaluation information for projects", "Analyzer-derived project-evaluation documentation check."),
    _check("assessment.internship_evaluation", "assessment", "Internship evaluation", 15, ANALYZER_DERIVED, "Evaluation information for internships", "Analyzer-derived internship-evaluation documentation check."),
    _check("assessment.practical_alignment", "assessment", "Practical-course assessment alignment", 10, ANALYZER_DERIVED, "Practical courses include practical/lab assessment", "Analyzer-derived alignment check using L-T-P and assessment keywords."),
    # Resources: 100 marks
    _check("resources.reference_coverage", "resources", "Courses with references/textbooks", 30, ANALYZER_DERIVED, "References for at least 80% of courses", "Analyzer-derived documentation coverage check."),
    _check("resources.labs_practicals", "resources", "Laboratory/practical availability", 25, ANALYZER_DERIVED, "Practical components present", "Analyzer-derived signal from practical hours and explicit lab titles/topics."),
    _check("resources.online_learning", "resources", "Online learning references", 15, ANALYZER_DERIVED, "NPTEL/SWAYAM or equivalent present", "Analyzer-derived deterministic keyword signal."),
    _check("resources.experimental", "resources", "Experimental components", 15, ANALYZER_DERIVED, "Experimental/laboratory components present", "Analyzer-derived deterministic practical-resource signal."),
    _check("resources.project_lab", "resources", "Project/lab resources", 15, ANALYZER_DERIVED, "Explicit project/lab resource evidence", "Analyzer-derived resource-description check."),
    # Skill coverage: 100 marks
    _check("skills.programming", "skill_coverage", "Programming", 8, AICTE_EXPLICIT, "Programming represented", "Programming is a supplied AICTE CSE core area."),
    _check("skills.data_structures_algorithms", "skill_coverage", "Data Structures & Algorithms", 8, AICTE_EXPLICIT, "DSA represented", "Data Structures and Algorithms is a supplied AICTE CSE core area."),
    _check("skills.mathematical_foundations", "skill_coverage", "Mathematical Foundations", 8, AICTE_EXPLICIT, "Discrete/mathematical foundations represented", "Discrete Mathematics is a supplied AICTE CSE core area."),
    _check("skills.computer_architecture", "skill_coverage", "Computer Architecture", 7, AICTE_EXPLICIT, "Architecture/organization represented", "Computer Organization and Architecture is a supplied AICTE CSE core area."),
    _check("skills.operating_systems", "skill_coverage", "Operating Systems", 8, AICTE_EXPLICIT, "Operating Systems represented", "Operating Systems is a supplied AICTE CSE core area."),
    _check("skills.databases", "skill_coverage", "Databases", 8, AICTE_EXPLICIT, "Database systems represented", "Database Systems is a supplied AICTE CSE core area."),
    _check("skills.computer_networks", "skill_coverage", "Computer Networks", 8, AICTE_EXPLICIT, "Computer Networks represented", "Computer Networks is a supplied AICTE CSE core area."),
    _check("skills.theory_computation", "skill_coverage", "Theory of Computation", 7, AICTE_EXPLICIT, "Theory of Computation represented", "Theory of Computation is a supplied AICTE CSE core area."),
    _check("skills.compiler_processing", "skill_coverage", "Compiler/Language Processing", 7, AICTE_EXPLICIT, "Compiler or language processing represented", "Compiler Design is a supplied AICTE CSE core area."),
    _check("skills.machine_learning_data", "skill_coverage", "Machine Learning/Data", 8, AICTE_EXPLICIT, "Machine Learning/Data represented", "Machine Learning is a supplied AICTE CSE core area."),
    _check("skills.cyber_security", "skill_coverage", "Cyber Security", 7, AICTE_EXPLICIT, "Cyber Security represented", "Cyber Security is a supplied AICTE CSE core area."),
    _check("skills.software_development", "skill_coverage", "Software/Application Development", 8, ANALYZER_DERIVED, "Software development represented", "Analyzer-derived CSE employability skill group."),
    _check("skills.projects_practical", "skill_coverage", "Projects/Practical Skills", 8, ANALYZER_DERIVED, "Project or substantial practical exposure represented", "Analyzer-derived applied-skill group."),
)

CHECKS_BY_ID: Dict[str, CheckDefinition] = {
    definition.check_id: definition for definition in CHECK_DEFINITIONS
}

COMPLIANCE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "compliance.induction": ("induction programme", "induction program", "student induction"),
    "compliance.environment": ("environmental science", "environment studies", "environmental studies"),
    "compliance.constitution_ikt": ("constitution of india", "indian knowledge", "traditional knowledge system"),
    "compliance.human_values": ("universal human values", "human values", "professional ethics"),
}

INDUSTRY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "industry.machine_learning": ("machine learning", "deep learning", "data science", "artificial intelligence"),
    "industry.cyber_security": ("cyber security", "cybersecurity", "information security", "network security"),
    "industry.cloud_distributed": ("cloud computing", "distributed system", "distributed computing", "microservices", "devops"),
    "industry.practical_programming": ("programming", "software development", "application development", "coding"),
    "industry.emerging_electives": ("machine learning", "deep learning", "cloud", "cyber", "blockchain", "internet of things", "iot", "big data", "data science", "devops", "natural language processing"),
}

SKILL_TAXONOMY: Dict[str, Tuple[str, ...]] = {
    "skills.programming": ("programming", "problem solving", "python", "java", "c programming", "object oriented"),
    "skills.data_structures_algorithms": ("data structure", "algorithm", "algorithm design", "algorithm analysis"),
    "skills.mathematical_foundations": ("discrete mathematics", "discrete math", "linear algebra", "probability", "statistics", "graph theory"),
    "skills.computer_architecture": ("computer organization", "computer architecture", "microprocessor", "digital logic"),
    "skills.operating_systems": ("operating system", "systems programming"),
    "skills.databases": ("database", "dbms", "data base", "sql", "data management"),
    "skills.computer_networks": ("computer network", "data communication", "networking", "network protocol"),
    "skills.theory_computation": ("theory of computation", "automata", "formal language", "computability"),
    "skills.compiler_processing": ("compiler", "language processor", "parsing", "syntax analysis"),
    "skills.machine_learning_data": ("machine learning", "data science", "artificial intelligence", "deep learning", "data mining"),
    "skills.cyber_security": ("cyber security", "cybersecurity", "information security", "cryptography", "network security"),
    "skills.software_development": ("software engineering", "software development", "web development", "mobile application", "application development", "devops"),
    "skills.projects_practical": ("project", "capstone", "laboratory", "lab", "practical", "internship"),
}

CORE_SKILL_IDS: Tuple[str, ...] = (
    "skills.programming",
    "skills.data_structures_algorithms",
    "skills.mathematical_foundations",
    "skills.computer_architecture",
    "skills.operating_systems",
    "skills.databases",
    "skills.computer_networks",
    "skills.theory_computation",
    "skills.compiler_processing",
    "skills.machine_learning_data",
    "skills.cyber_security",
)

ACTION_VERBS: Tuple[str, ...] = (
    "analyze", "apply", "build", "calculate", "classify", "compare", "create",
    "design", "develop", "evaluate", "explain", "identify", "implement", "model",
    "solve", "test", "use", "validate", "demonstrate", "construct",
)


def validate_scoring_configuration() -> None:
    if sum(CRITERION_WEIGHTS.values()) != 100:
        raise ValueError("Criterion weights must sum to 100")
    for criterion in CRITERION_WEIGHTS:
        total = sum(
            definition.maximum_marks
            for definition in CHECK_DEFINITIONS
            if definition.criterion == criterion
        )
        if total != 100:
            raise ValueError(f"Check marks for {criterion} must sum to 100, got {total}")
    if len(CHECKS_BY_ID) != len(CHECK_DEFINITIONS):
        raise ValueError("Analyzer check IDs must be unique")


validate_scoring_configuration()
