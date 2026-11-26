"""Authentication business logic: login, lockout, refresh rotation, logout, password change."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ValidationFailedError
from app.core.security import (
    REFRESH_TOKEN_DAYS, create_access_token, hash_password, hash_refresh_token,
    new_refresh_token, validate_password_strength, verify_password,
)
from app.models import RefreshToken, User
from app.services import audit_service

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
# Generic message: never reveal whether the email exists (prevents account enumeration).
INVALID_CREDENTIALS = "Incorrect email or password"


@dataclass
class TokenPair:
    access_token: str
    expires_in: int
    refresh_token: str


def _issue_tokens(db: Session, user: User, user_agent: str | None) -> TokenPair:
    access, expires_in = create_access_token(user.id)
    raw, token_hash = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, user_agent=(user_agent or "")[:300],
                        expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_DAYS)))
    return TokenPair(access, expires_in, raw)


def login(db: Session, email: str, password: str, ip: str | None, user_agent: str | None) -> TokenPair:
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))

    if user is None:
        audit_service.record(db, action="auth.login_failed", user_id=None, organization_id=None,
                             after={"email": email.strip().lower()}, ip_address=ip)
        db.commit()
        raise AuthenticationError(INVALID_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        raise AuthenticationError("Account temporarily locked after repeated failed logins. Try again later.")

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        locked = user.failed_login_count >= MAX_FAILED_LOGINS
        if locked:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        audit_service.record(db, action="auth.account_locked" if locked else "auth.login_failed",
                             user_id=user.id, organization_id=user.organization_id, entity_type="user",
                             entity_id=user.id, ip_address=ip)
        db.commit()  # failed attempts must be saved even though we raise
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not user.is_active:
        raise AuthenticationError("This account has been deactivated. Contact your administrator.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = _issue_tokens(db, user, user_agent)
    audit_service.record(db, action="auth.login", user_id=user.id, organization_id=user.organization_id,
                         entity_type="user", entity_id=user.id, ip_address=ip)
    db.commit()
    return tokens


def refresh(db: Session, raw_token: str | None, user_agent: str | None) -> TokenPair:
    """Exchange a refresh token for new tokens (rotation: the old one is revoked)."""
    if not raw_token:
        raise AuthenticationError("No session")
    now = datetime.now(UTC)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if stored is None:
        raise AuthenticationError("Invalid session")

    if stored.revoked_at is not None:
        # A revoked token is being reused: likely stolen. Revoke ALL of this user's sessions.
        db.execute(update(RefreshToken).where(RefreshToken.user_id == stored.user_id,
                                              RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
        audit_service.record(db, action="auth.refresh_token_reuse", user_id=stored.user_id,
                             organization_id=None, entity_type="user", entity_id=stored.user_id)
        db.commit()
        raise AuthenticationError("Session invalidated. Please log in again.")

    user = db.get(User, stored.user_id)
    if stored.expires_at <= now or user is None or not user.is_active:
        raise AuthenticationError("Session expired")

    stored.revoked_at = now
    tokens = _issue_tokens(db, user, user_agent)
    db.commit()
    return tokens


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        audit_service.record(db, action="auth.logout", user_id=stored.user_id, organization_id=None,
                             entity_type="user", entity_id=stored.user_id)
        db.commit()


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise ValidationFailedError("Current password is incorrect")
    try:
        validate_password_strength(new)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    user.password_hash = hash_password(new)
    user.must_change_password = False
    # Log out every other session after a password change.
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)))
    audit_service.record(db, action="auth.password_changed", user_id=user.id,
                         organization_id=user.organization_id, entity_type="user", entity_id=user.id)
    db.commit()
