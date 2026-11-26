"""Set a user's password from the terminal (typed hidden, stored as a hash).

    python -m scripts.set_password manager@demo.amcos.test
"""
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password, validate_password_strength
from app.database.session import SessionLocal
from app.models import AuditLog, User


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m scripts.set_password <email>")
    email = sys.argv[1].strip().lower()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        sys.exit(str(exc))
    with SessionLocal() as db, db.begin():
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            sys.exit(f"No user {email}.")
        user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        db.add(AuditLog(organization_id=user.organization_id, user_id=None, action="user.password_set_cli",
                        entity_type="user", entity_id=str(user.id)))
    print(f"Password updated for {email}.")


if __name__ == "__main__":
    main()
