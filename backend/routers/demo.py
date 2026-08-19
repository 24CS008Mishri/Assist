from fastapi import APIRouter, HTTPException, status

from backend.models.schemas import LoginRequest


router = APIRouter(prefix="/api", tags=["demo"])

USERS = [
    {"id": "u1", "name": "Meera Nair", "email": "meera.nair@aicte.gov.in", "password": "governance2026", "organization": "AICTE Headquarters", "role": "admin", "status": "Active"},
    {"id": "u2", "name": "Dr. Arvind Rao", "email": "arvind.rao@review.panel", "password": "governance2026", "organization": "National Review Panel", "role": "reviewer", "status": "Active"},
    {"id": "u3", "name": "Ananya Iyer", "email": "ananya.iyer@curriculum.lab", "password": "governance2026", "organization": "Curriculum Design Cell", "role": "designer", "status": "Active"},
    {"id": "u4", "name": "Rohan Kulkarni", "email": "rohan.k@institute.edu", "password": "governance2026", "organization": "Northstar Institute of Technology", "role": "institute", "status": "Active"},
]

CURRICULA = [
    {"id": "c1", "name": "B.Tech Artificial Intelligence", "program": "AI & Data Science", "version": "2.1", "designer": "Ananya Iyer", "status": "Under Review", "score": 82, "submitted": "18 Feb 2026"},
    {"id": "c2", "name": "B.Tech Computer Science & Engineering", "program": "Computer Science", "version": "1.4", "designer": "Ananya Iyer", "status": "Published", "score": 91, "submitted": "06 Jan 2026"},
    {"id": "c3", "name": "B.Tech Electronics & Communication Engineering", "program": "Electronics", "version": "1.1", "designer": "K. S. Menon", "status": "Changes Requested", "score": 74, "submitted": "28 Feb 2026"},
    {"id": "c4", "name": "B.Tech Artificial Intelligence", "program": "AI & Data Science", "version": "2.0", "designer": "A. Sen", "status": "Approved", "score": 88, "submitted": "12 Dec 2025"},
]

CHANGES = [
    {"id": "CR-1024", "course": "Data Structures", "issue": "Insufficient graph algorithm coverage.", "suggestion": "Add advanced graph algorithms.", "reason": "Students require additional preparation for advanced coursework.", "priority": "High", "status": "Submitted"},
    {"id": "CR-1018", "course": "DBMS", "issue": "Distributed systems module is brief.", "suggestion": "Add a practical transaction lab.", "reason": "Align lab exposure with current industry practice.", "priority": "Medium", "status": "Under Review"},
]


@router.get("/users")
def list_users():
    return [{key: value for key, value in user.items() if key != "password"} for user in USERS]


@router.get("/curricula")
def list_curricula():
    return CURRICULA


@router.get("/changes")
def list_changes():
    return CHANGES


@router.post("/login")
def login(request: LoginRequest):
    user = next((item for item in USERS if item["email"].lower() == request.email.strip().lower() and item["password"] == request.password), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return {
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "organization": user["organization"],
    }
