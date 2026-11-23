"""Read-only access to the audit trail and offline sync logs (writing is audit_service.record)."""
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, SyncLog, User
from app.services.scope import org_id


def list_audit(db: Session, actor: User, *, action: str | None, entity_type: str | None, entity_id: str | None,
               user_id: uuid.UUID | None, date_from: datetime | None, date_to: datetime | None, q: str | None,
               page: int, page_size: int):
    stmt = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id)
    # System admins (no organization) see everything; others only their AMCOS
    if actor.organization_id is not None:
        stmt = stmt.where(AuditLog.organization_id == actor.organization_id)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at < date_to)
    if q:
        stmt = stmt.where(or_(AuditLog.reason.ilike(f"%{q}%"), AuditLog.action.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def audit_actions(db: Session, actor: User) -> list[str]:
    stmt = select(AuditLog.action).distinct()
    if actor.organization_id is not None:
        stmt = stmt.where(AuditLog.organization_id == actor.organization_id)
    return sorted(db.scalars(stmt))


def sync_problems(db: Session, actor: User) -> list[tuple[SyncLog, str]]:
    """Sync requests in which records were rejected or in conflict, newest first."""
    return list(db.execute(
        select(SyncLog, User.full_name).join(User, User.id == SyncLog.user_id)
        .where(SyncLog.organization_id == org_id(actor), (SyncLog.conflicts + SyncLog.rejected) > 0)
        .order_by(SyncLog.created_at.desc()).limit(200)).all())
