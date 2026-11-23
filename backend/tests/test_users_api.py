from app.models import Organization

NEW_USER = {"email": "newclerk@test.amcos", "full_name": "New Clerk",
            "temporary_password": "TempPassw0rd1", "role_codes": ["clerk"]}


def test_clerk_cannot_list_or_create_users(client, make_user, login):
    make_user("clerk")
    h = login("clerk@test.amcos")
    assert client.get("/api/v1/users", headers=h).status_code == 403
    assert client.post("/api/v1/users", headers=h, json=NEW_USER).status_code == 403


def test_auditor_can_view_but_not_create(client, make_user, login):
    make_user("auditor")
    h = login("auditor@test.amcos")
    assert client.get("/api/v1/users", headers=h).status_code == 200
    assert client.post("/api/v1/users", headers=h, json=NEW_USER).status_code == 403


def test_manager_creates_user_in_own_organization(client, make_user, login, org):
    make_user("manager")
    h = login("manager@test.amcos")
    r = client.post("/api/v1/users", headers=h, json=NEW_USER)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["organization_id"] == str(org.id)
    assert body["must_change_password"] is True
    assert client.post("/api/v1/users", headers=h, json=NEW_USER).status_code == 409  # duplicate email


def test_manager_cannot_grant_system_admin(client, make_user, login):
    make_user("manager")
    r = client.post("/api/v1/users", headers=login("manager@test.amcos"),
                    json={**NEW_USER, "role_codes": ["system_admin"]})
    assert r.status_code == 403


def test_weak_password_rejected(client, make_user, login):
    make_user("manager")
    r = client.post("/api/v1/users", headers=login("manager@test.amcos"),
                    json={**NEW_USER, "temporary_password": "aaaaaaaaaaaa"})
    assert r.status_code == 422


def test_manager_cannot_see_other_organizations_users(client, make_user, login, db):
    other = Organization(name="Other AMCOS", code="OTH")
    db.add(other)
    db.flush()
    outsider = make_user("clerk", email="outsider@other.amcos", organization=other)
    make_user("manager")
    h = login("manager@test.amcos")
    emails = [u["email"] for u in client.get("/api/v1/users", headers=h).json()["items"]]
    assert "outsider@other.amcos" not in emails
    assert client.get(f"/api/v1/users/{outsider.id}", headers=h).status_code == 404


def test_deactivate_user_blocks_their_requests(client, make_user, login):
    clerk = make_user("clerk")
    manager = make_user("manager")
    clerk_h = login("clerk@test.amcos")
    mgr_h = login("manager@test.amcos")
    assert client.post(f"/api/v1/users/{manager.id}/status", headers=mgr_h,
                       json={"is_active": False, "reason": "self"}).status_code == 403
    r = client.post(f"/api/v1/users/{clerk.id}/status", headers=mgr_h,
                    json={"is_active": False, "reason": "Left the cooperative"})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=clerk_h).status_code == 401


def test_list_users_search_and_pagination(client, make_user, login):
    make_user("manager")
    make_user("clerk")
    h = login("manager@test.amcos")
    r = client.get("/api/v1/users?q=clerk&page_size=1", headers=h).json()
    assert r["total"] == 1 and len(r["items"]) == 1 and r["items"][0]["email"] == "clerk@test.amcos"
