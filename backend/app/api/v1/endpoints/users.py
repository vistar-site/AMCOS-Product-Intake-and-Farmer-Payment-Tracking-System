"""User management endpoints. Each declares the permission it needs."""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import User
from app.schemas.common import Page
from app.schemas.user import RoleRead, UserCreate, UserRead, UserStatusUpdate, UserUpdate
from app.services import user_service

router = APIRouter(tags=["users"])


@router.get("/users", response_model=Page[UserRead])
def list_users(
    q: str | None = Query(None, max_length=100, description="Search name or email"),
    role: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    actor: User = Depends(require_permission("user.view")),
    db: Session = Depends(get_db),
):
    items, total = user_service.list_users(db, actor, q=q, role=role, is_active=is_active,
                                           page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, actor: User = Depends(require_permission("user.manage")),
                db: Session = Depends(get_db)):
    return user_service.create_user(db, actor, body)


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: uuid.UUID, actor: User = Depends(require_permission("user.view")),
             db: Session = Depends(get_db)):
    return user_service.get_user(db, actor, user_id)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: uuid.UUID, body: UserUpdate, actor: User = Depends(require_permission("user.manage")),
                db: Session = Depends(get_db)):
    return user_service.update_user(db, actor, user_id, body)


@router.post("/users/{user_id}/status", response_model=UserRead)
def set_user_status(user_id: uuid.UUID, body: UserStatusUpdate,
                    actor: User = Depends(require_permission("user.manage")), db: Session = Depends(get_db)):
    return user_service.set_status(db, actor, user_id, body.is_active, body.reason)


@router.get("/roles", response_model=list[RoleRead])
def list_roles(_: User = Depends(require_permission("user.view")), db: Session = Depends(get_db)):
    return user_service.list_roles(db)
