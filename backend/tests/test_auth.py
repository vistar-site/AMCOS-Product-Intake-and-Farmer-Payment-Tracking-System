from sqlalchemy import select

from app.core.security import create_access_token
from app.models import AuditLog
from tests.conftest import TEST_PASSWORD


def test_login_success_returns_token_and_sets_httponly_cookie(client, make_user):
    make_user("clerk")
    r = client.post("/api/v1/auth/login", json={"email": "CLERK@test.amcos", "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    cookie = r.headers["set-cookie"]
    assert "amcos_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie


def test_wrong_password_and_unknown_email_give_same_message(client, make_user):
    make_user("clerk")
    a = client.post("/api/v1/auth/login", json={"email": "clerk@test.amcos", "password": "wrong"})
    b = client.post("/api/v1/auth/login", json={"email": "nobody@test.amcos", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_account_locks_after_five_failures(client, make_user, db):
    user = make_user("clerk")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"})
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert r.status_code == 401 and "locked" in r.json()["detail"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.account_locked",
                                            AuditLog.entity_id == str(user.id)))


def test_inactive_user_cannot_login(client, make_user):
    make_user("clerk", is_active=False)
    r = client.post("/api/v1/auth/login", json={"email": "clerk@test.amcos", "password": TEST_PASSWORD})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_forged_token_rejected(client, make_user):
    user = make_user("manager")
    token, _ = create_access_token(user.id)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_me_returns_permissions(client, make_user, login):
    make_user("clerk")
    r = client.get("/api/v1/auth/me", headers=login("clerk@test.amcos"))
    assert r.status_code == 200
    body = r.json()
    assert "delivery.create" in body["permissions"]
    assert "password_hash" not in body


def test_refresh_rotates_and_old_token_reuse_revokes_all(client, make_user):
    make_user("clerk")
    client.post("/api/v1/auth/login", json={"email": "clerk@test.amcos", "password": TEST_PASSWORD})
    old_cookie = client.cookies.get("amcos_refresh")

    r1 = client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200
    new_cookie = client.cookies.get("amcos_refresh")
    assert new_cookie != old_cookie

    # An attacker replays the old (already used) token -> every session is revoked
    client.cookies.set("amcos_refresh", old_cookie, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    client.cookies.set("amcos_refresh", new_cookie, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client, make_user):
    make_user("clerk")
    client.post("/api/v1/auth/login", json={"email": "clerk@test.amcos", "password": TEST_PASSWORD})
    cookie = client.cookies.get("amcos_refresh")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("amcos_refresh", cookie, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_change_password(client, make_user, login):
    make_user("clerk")
    headers = login("clerk@test.amcos")
    bad = client.post("/api/v1/auth/change-password", headers=headers,
                      json={"current_password": "nope", "new_password": "NewPassw0rd99"})
    assert bad.status_code == 422
    ok = client.post("/api/v1/auth/change-password", headers=headers,
                     json={"current_password": TEST_PASSWORD, "new_password": "NewPassw0rd99"})
    assert ok.status_code == 204
    r = client.post("/api/v1/auth/login", json={"email": "clerk@test.amcos", "password": "NewPassw0rd99"})
    assert r.status_code == 200


def test_login_rate_limited(client):
    codes = [client.post("/api/v1/auth/login", json={"email": "x@y.test", "password": "a"}).status_code
             for _ in range(11)]
    assert codes[-1] == 429


def test_login_accepts_reserved_test_domain(client, make_user):
    make_user("clerk", email="someone@unit.example.test")
    r = client.post("/api/v1/auth/login", json={"email": "someone@unit.example.test", "password": TEST_PASSWORD})
    assert r.status_code == 200
