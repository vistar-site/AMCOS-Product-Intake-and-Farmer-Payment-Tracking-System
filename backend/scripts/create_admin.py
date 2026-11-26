"""Create the first System Administrator safely (no hardcoded credentials).

    python -m scripts.create_admin --email admin@example.org --name "Jane Admin"

The password is typed interactively (hidden) and stored only as an Argon2 hash.
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from backend.app.database.core.security import hash_password, validate_password_strength
from app.database.session import SessionLocal
from app.models import AuditLog, Role, User
from scripts.bootstrap import sync_roles_and_permissions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    password = getpass.getpass("New admin password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        sys.exit(str(exc))

    with SessionLocal() as db, db.begin():
        sync_roles_and_permissions(db)
        email = args.email.strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            sys.exit(f"A user with email {email} already exists.")
        role = db.scalar(select(Role).where(Role.code == "system_admin"))
        user = User(email=email, full_name=args.name, password_hash=hash_password(password), roles=[role])
        db.add(user)
        db.flush()  # sends INSERT so user.id exists, still inside the transaction
        db.add(AuditLog(user_id=user.id, action="user.create_admin", entity_type="user",
                        entity_id=str(user.id), after={"email": email}))
    print(f"System administrator {email} created.")


if __name__ == "__main__":
    main()
