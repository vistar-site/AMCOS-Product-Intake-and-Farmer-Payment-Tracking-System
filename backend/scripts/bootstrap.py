"""Sync roles and permissions from app/core/permissions.py into the database.

Safe to run any number of times (idempotent): it inserts missing rows and
updates role->permission links, never deletes users or business data.

    python -m scripts.bootstrap
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSIONS, ROLES
from app.database.session import SessionLocal
from app.models import Permission, Role


def sync_roles_and_permissions(db: Session) -> None:
    existing = {p.code: p for p in db.scalars(select(Permission))}
    for code, description in PERMISSIONS.items():
        if code in existing:
            existing[code].description = description
        else:
            existing[code] = Permission(code=code, description=description)
            db.add(existing[code])

    roles = {r.code: r for r in db.scalars(select(Role))}
    for code, spec in ROLES.items():
        role = roles.get(code) or Role(code=code, name=spec["name"])
        role.name = spec["name"]
        role.permissions = [existing[p] for p in sorted(spec["permissions"])]
        db.add(role)


def main() -> None:
    with SessionLocal() as db, db.begin():  # db.begin(): commit on success, rollback on error
        sync_roles_and_permissions(db)
    print(f"Synced {len(PERMISSIONS)} permissions and {len(ROLES)} roles.")


if __name__ == "__main__":
    main()
