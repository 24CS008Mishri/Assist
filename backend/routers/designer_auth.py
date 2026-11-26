from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.core.designer_sessions import enabled, revoke, session_identity, verified_login
from backend.routers.live_assistant import close_designer_consultation

router = APIRouter(prefix="/api/designer-auth", tags=["designer-auth"])


class DesignerLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(body: DesignerLogin, request: Request, response: Response):
    if not enabled():
        raise HTTPException(503, "Verified Designer sign-in is unavailable.")
    profile = verified_login(body.email.strip().lower(), body.password, request, response)
    if profile is None:
        raise HTTPException(401, "Invalid email or password")
    return profile


@router.post("/logout", status_code=204)
def logout(request: Request, tasks: BackgroundTasks):
    identity = session_identity(request)
    response = Response(status_code=204)
    revoke(request, response)
    if identity:
        tasks.add_task(close_designer_consultation, identity["id"])
    return response
