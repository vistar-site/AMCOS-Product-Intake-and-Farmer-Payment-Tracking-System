"""Passwords (Argon2) and tokens (JWT access tokens + opaque refresh tokens).

Two-token design:
- ACCESS token: short-lived JWT (15 min), sent as "Authorization: Bearer ...".
  Signed with SECRET_KEY, so the server can verify it without a DB lookup.
  Kept only in browser memory (not localStorage) to limit XSS theft.
- REFRESH token: long random string in an httpOnly cookie (JavaScript cannot
  read it). Only its SHA-256 hash is stored in refresh_tokens, so a database
  leak does not reveal usable tokens. Rotated on every use; revocable on logout.
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_hasher = PasswordHash.recommended()  # Argon2id

MIN_PASSWORD_LENGTH = 10
JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_DAYS = 7


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def validate_password_strength(plain: str) -> None:
    if len(plain) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if plain.isdigit() or plain.isalpha():
        raise ValueError("Password must contain both letters and numbers")


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (token, lifetime_seconds)."""
    minutes = get_settings().access_token_expire_minutes
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes), "type": "access"}
    return jwt.encode(payload, get_settings().secret_key, algorithm=JWT_ALGORITHM), minutes * 60


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the user id, or None if the token is invalid/expired/tampered."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the cookie, hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
