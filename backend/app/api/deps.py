"""FastAPI dependencies shared by endpoints: current user and permission checks.

Usage in an endpoint:
    def list_users(user: User = Depends(require_permission("user.view"))): ...

FastAPI runs the dependency BEFORE the endpoint body. If the token is missing or
the permission is absent, the request is rejected (401/403) and the endpoint
never runs. This is the backend enforcement: hiding a button in React is only UX.
"""
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AuthenticationError("Session expired or invalid token")
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions), selectinload(User.centres))
    )
    # Re-checked on every request: deactivating a user takes effect within one request.
    if user is None or not user.is_active:
        raise AuthenticationError("Account inactive")
    return user


def require_permission(*codes: str) -> Callable[..., User]:
    """Dependency factory: the user must hold ALL listed permission codes."""

    def checker(user: User = Depends(get_current_user)) -> User:
        missing = set(codes) - user.permission_codes
        if missing:
            raise PermissionDeniedError(f"Missing permission: {', '.join(sorted(missing))}")
        return user

    return checker
