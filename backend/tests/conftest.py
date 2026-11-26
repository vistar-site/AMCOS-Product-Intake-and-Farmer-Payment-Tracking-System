"""Test fixtures.

`db` gives each test a session inside a transaction that is ROLLED BACK at the
end, so tests can insert freely without leaving rows behind. Service code that
calls commit() only commits a SAVEPOINT inside that outer transaction.

`client` is an HTTP test client whose requests use that same session.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.security import hash_password
from app.database.session import engine, get_db
from app.main import app
from app.models import CollectionCentre, Organization, Role, User

TEST_PASSWORD = "TestPassw0rd!"
_PW_HASH = hash_password(TEST_PASSWORD)  # hash once: Argon2 is deliberately slow


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    rate_limit.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def org(db):
    o = Organization(name="Test AMCOS", code="TST")
    db.add(o)
    db.flush()
    db.add(CollectionCentre(organization_id=o.id, code="C1", name="Centre One"))
    db.flush()
    return o


@pytest.fixture
def make_user(db, org):
    def _make(role_code: str, email: str | None = None, organization=org, **kw) -> User:
        role = db.scalar(select(Role).where(Role.code == role_code))
        user = User(organization_id=organization.id if organization else None,
                    email=email or f"{role_code}@test.amcos", full_name=f"Test {role_code}",
                    password_hash=_PW_HASH, roles=[role], **kw)
        db.add(user)
        db.flush()
        return user
    return _make


@pytest.fixture
def login(client):
    """Returns auth headers for an email (password = TEST_PASSWORD)."""
    def _login(email: str) -> dict:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _login
