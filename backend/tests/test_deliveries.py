import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import CollectionCentre, Crop, CropGrade, Delivery, Farmer, Season, SyncLog


@pytest.fixture
def setup(db, org, make_user, login):
    """A centre, an active season covering today, cashew with grades, one farmer, a clerk and a manager."""
    centre = db.scalar(select(CollectionCentre).where(CollectionCentre.organization_id == org.id))
    other_centre = CollectionCentre(organization_id=org.id, code="C2", name="Centre Two")
    today = date.today()
    season = Season(organization_id=org.id, name="TEST", start_date=today - timedelta(days=60),
                    end_date=today + timedelta(days=60))
    crop = Crop(organization_id=org.id, code="CASHEW", name="Cashew", rules={"max_gross_kg": 500},
                grades=[CropGrade(code="STD", name="Standard")])
    farmer = Farmer(organization_id=org.id, membership_no="T-0001", full_name="Asha Farmer",
                    phone="+255700000001", mobile_money_number="+255700000001", home_centre_id=centre.id)
    db.add_all([other_centre, season, crop, farmer])
    db.flush()
    clerk = make_user("clerk")
    clerk.centres = [centre]
    make_user("manager")
    db.flush()
    return {"centre": centre, "other_centre": other_centre, "season": season, "crop": crop, "farmer": farmer,
            "clerk_h": login("clerk@test.amcos"), "manager_h": login("manager@test.amcos")}


def payload(s, **over):
    body = {"id": str(uuid.uuid4()), "farmer_id": str(s["farmer"].id), "centre_id": str(s["centre"].id),
            "crop_id": str(s["crop"].id), "gross_weight": "82.500", "tare_weight": "0.500",
            "captured_at": datetime.now(UTC).isoformat()}
    return body | over


def test_record_delivery_computes_net_and_receipt_number(client, setup):
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup))
    assert r.status_code == 201, r.text
    d = r.json()["delivery"]
    assert d["net_weight"] == "82.000"          # decimals travel as strings
    assert d["receipt_no"] == f"TST-{datetime.now().year}-000001"
    assert d["season"]["name"] == "TEST"         # resolved automatically from the date
    r2 = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup, gross_weight="10"))
    assert r2.json()["delivery"]["receipt_no"].endswith("000002")


def test_same_id_twice_is_idempotent(client, setup, db):
    body = payload(setup)
    first = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=body)
    again = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=body)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["delivery"]["receipt_no"] == first.json()["delivery"]["receipt_no"]
    assert db.scalar(select(Delivery).where(Delivery.id == uuid.UUID(body["id"]))) is not None


def test_same_id_with_different_weight_is_a_conflict_not_an_overwrite(client, setup):
    body = payload(setup)
    client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=body)
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=body | {"gross_weight": "99"})
    assert r.status_code == 409
    d = client.get(f"/api/v1/deliveries/{body['id']}", headers=setup["clerk_h"]).json()
    assert d["gross_weight"] == "82.500"   # original untouched


@pytest.mark.parametrize("over,fragment", [
    ({"gross_weight": "5", "tare_weight": "5"}, "Net weight"),
    ({"gross_weight": "0"}, "greater than 0"),
    ({"gross_weight": "600"}, "500 kg limit"),
    ({"captured_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()}, "future"),
    ({"captured_at": "2026-01-01T10:00:00"}, "timezone"),
])
def test_invalid_deliveries_rejected(client, setup, over, fragment):
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup, **over))
    assert r.status_code == 422
    assert fragment in r.text


def test_inactive_farmer_rejected(client, setup, db):
    setup["farmer"].status = "inactive"
    db.flush()
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup))
    assert r.status_code == 422 and "inactive" in r.json()["detail"]


def test_grade_must_belong_to_crop(client, setup):
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup, grade_id=str(uuid.uuid4())))
    assert r.status_code == 422


def test_clerk_cannot_record_at_unassigned_centre(client, setup):
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"],
                    json=payload(setup, centre_id=str(setup["other_centre"].id)))
    assert r.status_code == 403


def test_duplicate_warning(client, setup):
    client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup))
    r = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup))
    assert r.status_code == 201
    assert any("Possible duplicate" in w for w in r.json()["warnings"])


def test_sync_batch_handles_each_record_independently(client, setup, db):
    already = payload(setup)
    client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=already)
    batch = [
        payload(setup, provisional_receipt_no="OFF-AB12-0001"),       # new -> created
        already,                                                      # replay -> duplicate
        already | {"id": already["id"], "gross_weight": "70"},        # same id, new content -> conflict
        payload(setup, gross_weight="900"),                           # over crop limit -> rejected
    ]
    r = client.post("/api/v1/sync/deliveries", headers=setup["clerk_h"],
                    json={"device_id": "tablet-1", "deliveries": batch})
    assert r.status_code == 200, r.text
    statuses = [x["status"] for x in r.json()["results"]]
    assert statuses == ["created", "duplicate", "conflict", "rejected"]
    created = db.get(Delivery, uuid.UUID(batch[0]["id"]))
    assert created.source == "offline_sync" and created.provisional_receipt_no == "OFF-AB12-0001"
    assert created.received_at is not None and created.device_id == "tablet-1"
    log = db.scalar(select(SyncLog).where(SyncLog.device_id == "tablet-1"))
    assert (log.created, log.duplicates, log.conflicts, log.rejected) == (1, 1, 1, 1)


def test_amendment_workflow_requires_a_second_person(client, setup, make_user, login):
    d = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup)).json()["delivery"]
    r = client.post(f"/api/v1/deliveries/{d['id']}/amendments", headers=setup["clerk_h"],
                    json={"gross_weight": "80.500", "reason": "Scale was not zeroed"})
    assert r.status_code == 201, r.text
    amendment = r.json()["amendments"][0]
    assert r.json()["gross_weight"] == "82.500"     # nothing changes until approved

    # The clerk lacks approval permission
    url = f"/api/v1/deliveries/{d['id']}/amendments/{amendment['id']}/review"
    assert client.post(url, headers=setup["clerk_h"], json={"decision": "approve"}).status_code == 403

    ok = client.post(url, headers=setup["manager_h"], json={"decision": "approve", "note": "Verified"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["gross_weight"] == "80.500" and body["net_weight"] == "80.000"
    assert body["amendments"][0]["old_values"]["gross_weight"] == "82.500"   # history preserved
    assert client.post(url, headers=setup["manager_h"], json={"decision": "approve"}).status_code == 409


def test_void_needs_permission_and_reason(client, setup):
    d = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup)).json()["delivery"]
    url = f"/api/v1/deliveries/{d['id']}/void"
    assert client.post(url, headers=setup["clerk_h"], json={"reason": "Mistake entry"}).status_code == 403
    assert client.post(url, headers=setup["manager_h"], json={"reason": "x"}).status_code == 422
    r = client.post(url, headers=setup["manager_h"], json={"reason": "Recorded for wrong farmer"})
    assert r.json()["status"] == "voided"
    listed = client.get("/api/v1/deliveries", headers=setup["manager_h"]).json()
    assert listed["total"] == 1 and listed["total_net_weight"] == "0"   # voided excluded from totals


def test_receipt_pdf(client, setup):
    d = client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup)).json()["delivery"]
    r = client.get(f"/api/v1/deliveries/{d['id']}/receipt.pdf", headers=setup["clerk_h"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_clerk_only_sees_own_centre_deliveries(client, setup):
    client.post("/api/v1/deliveries", headers=setup["manager_h"],
                json=payload(setup, centre_id=str(setup["other_centre"].id)))
    client.post("/api/v1/deliveries", headers=setup["clerk_h"], json=payload(setup, gross_weight="20"))
    assert client.get("/api/v1/deliveries", headers=setup["clerk_h"]).json()["total"] == 1
    assert client.get("/api/v1/deliveries", headers=setup["manager_h"]).json()["total"] == 2


def test_farmer_payment_details_hidden_from_clerk(client, setup):
    fid = setup["farmer"].id
    clerk_view = client.get(f"/api/v1/farmers/{fid}", headers=setup["clerk_h"]).json()
    manager_view = client.get(f"/api/v1/farmers/{fid}", headers=setup["manager_h"]).json()
    assert "mobile_money_number" not in clerk_view
    assert manager_view["mobile_money_number"] == "+255700000001"


def test_register_farmer_auto_number_and_phone_normalization(client, setup):
    r = client.post("/api/v1/farmers", headers=setup["clerk_h"],
                    json={"full_name": "Juma Mpya", "phone": "0712345678", "village": "Nanyamba",
                          "home_centre_id": str(setup["centre"].id)})
    assert r.status_code == 201, r.text
    assert r.json()["membership_no"].startswith("TST-")
    assert r.json()["phone"] == "+255712345678"
    dup = client.post("/api/v1/farmers", headers=setup["manager_h"],
                      json={"full_name": "Someone Else", "membership_no": "t-0001"})
    assert dup.status_code == 409   # case-insensitive: stored upper-case


def test_farmer_search_by_name_member_no_and_phone(client, setup):
    h = setup["clerk_h"]
    for q in ("asha", "T-0001", "0700000001", "+255700000001"):
        assert client.get(f"/api/v1/farmers?q={q}", headers=h).json()["total"] == 1, q


def test_season_overlap_rejected(client, setup):
    r = client.post("/api/v1/seasons", headers=setup["manager_h"],
                    json={"name": "Overlap", "start_date": str(date.today()), "end_date": str(date.today())})
    assert r.status_code == 422


def test_clerk_cannot_configure_crops(client, setup):
    r = client.post("/api/v1/crops", headers=setup["clerk_h"], json={"code": "MAIZE", "name": "Maize"})
    assert r.status_code == 403


def test_centre_staff_assignment(client, setup, db):
    clerk_id = client.get("/api/v1/auth/me", headers=setup["clerk_h"]).json()["id"]
    r = client.put(f"/api/v1/centres/{setup['other_centre'].id}/staff", headers=setup["manager_h"],
                   json={"user_ids": [clerk_id]})
    assert r.status_code == 200 and r.json()["users"][0]["id"] == clerk_id
