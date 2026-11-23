"""Single helper that every service uses to write audit records.

It only ADDS the row to the session; the caller's transaction commits it together
with the business change, so either both are saved or neither is.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    action: str,
    user_id: uuid.UUID | None,
    organization_id: uuid.UUID | None,
    entity_type: str | None = None,
    entity_id: Any = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(AuditLog(
        action=action, user_id=user_id, organization_id=organization_id, entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before, after=after, reason=reason, ip_address=ip_address,
    ))
