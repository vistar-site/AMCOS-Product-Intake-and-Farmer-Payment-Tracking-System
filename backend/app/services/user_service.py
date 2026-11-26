"""User management rules.

Organization scoping: a manager only ever sees/edits users of their own AMCOS.
System admins (organization_id IS NULL) can manage any organization.
"""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.database.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from backend.app.database.core.security import hash_password, validate_password_strength
from app.models import CollectionCentre, Role, User
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit_service

PRIVILEGED_ROLES = {"system_admin"}


def is_system_admin(user: User) -> bool:
    return user.organization_id is None and "system_admin" in {r.code for r in user.roles}


def _snapshot(u: User) -> dict:
    return {"email": u.email, "full_name": u.full_name, "phone": u.phone, "is_active": u.is_active,
            "roles": sorted(r.code for r in u.roles), "centres": sorted(c.code for c in u.centres)}


def _load(db: Session, actor: User, user_id: uuid.UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id)
                     .options(selectinload(User.roles), selectinload(User.centres)))
    # Users of another AMCOS are reported as "not found" (don't leak their existence).
    if user is None or (not is_system_admin(actor) and user.organization_id != actor.organization_id):
        raise NotFoundError("User not found")
    return user


def _resolve_roles(db: Session, actor: User, codes: list[str]) -> list[Role]:
    roles = list(db.scalars(select(Role).where(Role.code.in_(codes))))
    if len(roles) != len(set(codes)):
        raise ValidationFailedError("Unknown role code")
    if not is_system_admin(actor) and PRIVILEGED_ROLES & set(codes):
        raise PermissionDeniedError("Only a system administrator can assign the system_admin role")
    return roles


def _resolve_centres(db: Session, org_id: uuid.UUID | None, ids: list[uuid.UUID]) -> list[CollectionCentre]:
    if not ids:
        return []
    centres = list(db.scalars(select(CollectionCentre).where(
        CollectionCentre.id.in_(ids), CollectionCentre.organization_id == org_id)))
    if len(centres) != len(set(ids)):
        raise ValidationFailedError("Collection centre not found in this AMCOS")
    return centres


def list_users(db: Session, actor: User, *, q: str | None, role: str | None, is_active: bool | None,
               page: int, page_size: int) -> tuple[list[User], int]:
    stmt = select(User)
    if not is_system_admin(actor):
        stmt = stmt.where(User.organization_id == actor.organization_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if role:
        stmt = stmt.where(User.roles.any(Role.code == role))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.options(selectinload(User.roles), selectinload(User.centres))
                       .order_by(User.full_name).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total or 0


def get_user(db: Session, actor: User, user_id: uuid.UUID) -> User:
    return _load(db, actor, user_id)


def create_user(db: Session, actor: User, data: UserCreate) -> User:
    org_id = data.organization_id if is_system_admin(actor) else actor.organization_id
    email = data.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("A user with this email already exists")
    try:
        validate_password_strength(data.temporary_password)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc

    user = User(organization_id=org_id, email=email, full_name=data.full_name.strip(), phone=data.phone,
                password_hash=hash_password(data.temporary_password), must_change_password=True,
                roles=_resolve_roles(db, actor, data.role_codes),
                centres=_resolve_centres(db, org_id, data.centre_ids))
    db.add(user)
    db.flush()
    audit_service.record(db, action="user.create", user_id=actor.id, organization_id=org_id,
                         entity_type="user", entity_id=user.id, after=_snapshot(user))
    db.commit()
    return user


def update_user(db: Session, actor: User, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = _load(db, actor, user_id)
    before = _snapshot(user)
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        user.phone = data.phone
    if data.role_codes is not None:
        if user.id == actor.id:
            raise PermissionDeniedError("You cannot change your own roles")
        user.roles = _resolve_roles(db, actor, data.role_codes)
    if data.centre_ids is not None:
        user.centres = _resolve_centres(db, user.organization_id, data.centre_ids)
    audit_service.record(db, action="user.update", user_id=actor.id, organization_id=user.organization_id,
                         entity_type="user", entity_id=user.id, before=before, after=_snapshot(user))
    db.commit()
    return user


def set_status(db: Session, actor: User, user_id: uuid.UUID, is_active: bool, reason: str) -> User:
    user = _load(db, actor, user_id)
    if user.id == actor.id:
        raise PermissionDeniedError("You cannot deactivate your own account")
    before = _snapshot(user)
    user.is_active = is_active
    if is_active:
        user.failed_login_count, user.locked_until = 0, None
    audit_service.record(db, action="user.activate" if is_active else "user.deactivate", user_id=actor.id,
                         organization_id=user.organization_id, entity_type="user", entity_id=user.id,
                         before=before, after=_snapshot(user), reason=reason)
    db.commit()
    return user


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)))
