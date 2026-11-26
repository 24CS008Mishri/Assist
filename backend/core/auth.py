import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status

from backend.core.designer_sessions import enabled as verified_designer_enabled, local_video_enabled, session_identity

load_dotenv()
@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity validated by the application's server-side auth middleware."""

    user_id: str
    role: str
    name: Optional[str] = None
    email: Optional[str] = None


_ROLE_ALIASES = {
    "aicte admin": "admin",
    "curriculum designer": "designer",
    "institute representative": "institute",
    "reviewer / expert": "reviewer",
}
_DEMO_IDENTITY_HEADER = "X-Demo-User-Id"


def _identity_value(identity: Any, *names: str) -> Any:
    if isinstance(identity, Mapping):
        return next((identity.get(name) for name in names if identity.get(name)), None)
    return next(
        (getattr(identity, name, None) for name in names if getattr(identity, name, None)),
        None,
    )


def _normalized_role(value: Any) -> str:
    resolved = getattr(value, "value", value)
    normalized = str(resolved or "").strip().lower()
    return _ROLE_ALIASES.get(normalized, normalized)


def _server_identity(request: Request) -> Any:
    for name in ("authenticated_user", "current_user", "user"):
        identity = getattr(request.state, name, None)
        if identity is not None:
            return identity
    identity = request.scope.get("user")
    if identity is not None and getattr(identity, "is_authenticated", True):
        return identity
    return session_identity(request)


def _demo_identity_enabled() -> bool:
    return os.getenv("ENABLE_DEMO_IDENTITY_ADAPTER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _demo_identity(request: Request) -> Optional[Mapping[str, Any]]:
    """Resolve the existing demo registry only when explicitly enabled.

    DEVELOPMENT/DEMO ONLY: Replace this adapter with teammate authentication
    identity provider when merged. Production remains fail-closed by default.
    """
    if not _demo_identity_enabled():
        return None
    user_id = request.headers.get(_DEMO_IDENTITY_HEADER, "").strip()
    if not user_id:
        return None

    # Keep compatibility with existing demo sessions, while MongoDB becomes
    # authoritative for role and account state after the identity is migrated.
    from backend.routers.demo import USERS
    from backend.services.workflow_service import find_user

    try:
        record = find_user(user_id)
    except Exception:
        return None
    if record:
        if record.get("status") != "Active":
            return None
        return record
    
    return next(
        (
            user
            for user in USERS
            if user.get("id") == user_id and user.get("status") == "Active"
            and not (user.get("role") == "designer" and (verified_designer_enabled() or local_video_enabled()))
        ),
        None,
    )


def get_current_identity(request: Request) -> Optional[AuthenticatedUser]:
    """Normalize teammate-auth identity, with an explicit demo-only fallback."""
    identity = _server_identity(request)
    if identity is None:
        identity = _demo_identity(request)
    return _normalize_identity(identity)


def _normalize_identity(identity: Any) -> Optional[AuthenticatedUser]:
    if identity is None:
        return None

    user_id = _identity_value(identity, "user_id", "id", "sub")
    role = _normalized_role(_identity_value(identity, "role"))
    if not user_id or not role:
        return None
    name = _identity_value(identity, "name", "display_name")
    email = _identity_value(identity, "email", "username")
    return AuthenticatedUser(
        user_id=str(user_id),
        role=role,
        name=str(name) if name else None,
        email=str(email).strip().lower() if email else None,
    )


def require_authenticated_user(request: Request) -> AuthenticatedUser:
    """Require teammate-auth identity or the explicit development adapter."""
    identity = get_current_identity(request)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return identity


def require_verified_designer(request: Request) -> AuthenticatedUser:
    identity = _normalize_identity(_server_identity(request))
    if identity is None:
        raise HTTPException(status_code=401, detail="Sign in with a verified Designer account to start a consultation.")
    require_role(identity, "designer")
    return identity


def require_role(user: AuthenticatedUser, *allowed_roles: str) -> None:
    allowed = {role.strip().lower() for role in allowed_roles}
    if user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not authorized for the requested operation",
        )
