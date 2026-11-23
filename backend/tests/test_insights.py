"""Phase 8: dashboard, reports, SMS notifications, settings, audit trail, sync review."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D

from sqlalchemy import select

from app.models import CollectionCentre, SmsMessage
from app.services import notification_service
from tests.test_finance import sell_everything
from tests.test_warehouse_auction import new_batch, world  # noqa: F401


def _deliver(client, w, farmer, kg="50"):
    centre = w["centre"]
    r = client.post("/api/v1/deliveries", headers=w["h"]["mgr"], json={
        "id": str(uuid.uuid4()), "farmer_id": str(farmer.id), "centre_id": str(centre.id), "crop_id": str(w["crop"].id),
        "gross_weight": kg, "captured_at": datetime.now(UTC).isoformat()})
    assert r.status_code == 201, r.text
    return r.json()["delivery"]


def test_dashboard_and_reports_from_real_records(client, world, make_user, login):  # noqa: F811
    w, h = world, world["h"]
    make_user("auditor")
    h["aud"] = login("auditor@test.amcos")
    sell_everything(client, w)            # 1,000 kg delivered; 980 kg sold for 2,001,000.00

    d = client.get("/api/v1/dashboard", headers=h["mgr"]).json()
    assert D(d["collected_kg"]) == D("1000") and d["deliveries"] == 3
    assert D(d["at_warehouse_kg"]) == D("1000") and D(d["awaiting_dispatch_kg"]) == 0
    assert d["finance"]["auction_value"] == "2001000.00" and d["finance"]["sold_kg"] == "980.000"
    assert {c["name"] for c in d["by_crop"]} == {"Cashew"}
    assert any(t["link"] == "/warehouse" for t in d["tasks"])          # open discrepancy from the -8 kg receipt
    # crop filter with no data
    other = client.get(f"/api/v1/dashboard?crop_id={w['other_crop'].id}", headers=h["mgr"]).json()
    assert other["deliveries"] == 0
    # clerk sees operations but no money
    assert client.get("/api/v1/dashboard", headers=h["clerk"]).json()["finance"] is None

    cat = {r["code"] for r in client.get("/api/v1/reports", headers=h["mgr"]).json()}
    assert {"intake", "auction_sales", "earnings", "reconciliation"} <= cat
    for code in cat:                                                    # every report runs
        r = client.get(f"/api/v1/reports/{code}", headers=h["mgr"])
        assert r.status_code == 200, (code, r.text)
    intake = client.get("/api/v1/reports/intake", headers=h["mgr"]).json()
    assert intake["row_count"] == 3 and intake["totals"]["net"] == "1000.000"
    sales = client.get("/api/v1/reports/auction_sales", headers=h["aud"]).json()  # auditor allowed
    assert sales["totals"]["value"] == "2001000.00"

    for fmt, ctype, magic in (("csv", "text/csv", b"\xef\xbb\xbf"), ("xlsx", "spreadsheetml", b"PK"), ("pdf", "application/pdf", b"%PDF")):
        r = client.get(f"/api/v1/reports/auction_sales/export?format={fmt}", headers=h["mgr"])
        assert r.status_code == 200 and ctype in r.headers["content-type"] and r.content.startswith(magic), fmt

    # clerk has neither operational nor financial report permission
    assert client.get("/api/v1/reports/intake", headers=h["clerk"]).status_code == 403
    assert client.get("/api/v1/reports/earnings", headers=h["wh"]).status_code == 403    # warehouse: operational only
    assert client.get("/api/v1/reports/receipts", headers=h["wh"]).status_code == 200


def test_delivery_sms_is_queued_then_simulated(client, world, db):  # noqa: F811
    w = world
    farmer = w["farmers"][0]
    farmer.phone = "+255712345678"
    db.flush()
    d = _deliver(client, w, farmer, "82.5")
    msg = db.scalar(select(SmsMessage).where(SmsMessage.related_id == d["id"]))
    assert msg is not None and msg.status in ("queued", "simulated")
    assert d["receipt_no"] in msg.body and "82.5" in msg.body and "Tumepokea" in msg.body   # Swahili default
    notification_service.process_queue(db, w["centre"].organization_id)
    db.refresh(msg)
    assert msg.status == "simulated" and msg.provider == "mock"    # never claims a real send


def test_sms_failure_retries_then_fails(client, world, db):  # noqa: F811
    w = world
    farmer = w["farmers"][1]
    farmer.phone = "+255700000000"   # mock provider fails numbers ending in 000
    db.flush()
    d = _deliver(client, w, farmer)
    msg = db.scalar(select(SmsMessage).where(SmsMessage.related_id == d["id"]))
    org = w["centre"].organization_id
    for _ in range(3):
        msg.next_attempt_at = None if msg.status == "queued" else msg.next_attempt_at  # make due now
        db.flush()
        notification_service.process_queue(db, org)
        db.refresh(msg)
    assert msg.status == "failed" and msg.attempts == 3 and "Simulated failure" in msg.last_error
    r = client.post(f"/api/v1/notifications/messages/{msg.id}/retry", headers=w["h"]["mgr"])
    assert r.status_code == 200 and r.json()["status"] == "queued"


def test_settings_control_sms_and_are_validated(client, world, db):  # noqa: F811
    w, h = world, world["h"]
    farmer = w["farmers"][2]
    farmer.phone = "+255712000111"
    db.flush()
    assert client.put("/api/v1/settings", headers=h["mgr"], json={"values": {"sms.delivery_receipt": False}}).status_code == 200
    d = _deliver(client, w, farmer)
    assert db.scalar(select(SmsMessage).where(SmsMessage.related_id == d["id"])) is None
    assert client.put("/api/v1/settings", headers=h["mgr"], json={"values": {"sms.max_attempts": 99}}).status_code == 422
    assert client.put("/api/v1/settings", headers=h["mgr"], json={"values": {"nonsense.key": 1}}).status_code == 422
    assert client.put("/api/v1/settings", headers=h["clerk"], json={"values": {"sms.enabled": False}}).status_code == 403
    vals = {s["key"]: s["value"] for s in client.get("/api/v1/settings", headers=h["clerk"]).json()}
    assert vals["sms.delivery_receipt"] is False and vals["sms.enabled"] is True


def test_template_placeholders_validated(client, world):  # noqa: F811
    h = world["h"]
    url = "/api/v1/notifications/templates/DELIVERY_RECEIPT/en"
    assert client.put(url, headers=h["mgr"], json={"body": "Hello {farmer}, ref {bank_pin}"}).status_code == 422
    r = client.put(url, headers=h["mgr"], json={"body": "{org}: {net} kg {crop} received. Receipt {receipt}."})
    assert r.status_code == 200
    t = next(x for x in r.json() if x["code"] == "DELIVERY_RECEIPT" and x["language"] == "en")
    assert t["is_default"] is False


def test_audit_trail_access(client, world, make_user, login):  # noqa: F811
    w, h = world, world["h"]
    make_user("auditor")
    aud = login("auditor@test.amcos")
    d = _deliver(client, w, w["farmers"][0])
    r = client.get(f"/api/v1/audit-logs?entity_id={d['id']}", headers=aud)
    assert r.status_code == 200
    assert [i["action"] for i in r.json()["items"]] == ["delivery.create"]
    assert r.json()["items"][0]["user_name"] == "Test manager"
    assert client.get("/api/v1/audit-logs", headers=h["clerk"]).status_code == 403
    assert "delivery.create" in client.get("/api/v1/audit-logs/actions", headers=aud).json()


def test_sync_problems_visible_to_managers(client, world):  # noqa: F811
    w, h = world, world["h"]
    farmer = w["farmers"][0]
    bad = {"id": str(uuid.uuid4()), "farmer_id": str(farmer.id), "centre_id": str(uuid.uuid4()), "crop_id": str(w["crop"].id),
           "gross_weight": "10", "captured_at": datetime.now(UTC).isoformat()}
    r = client.post("/api/v1/sync/deliveries", headers=h["mgr"], json={"device_id": "tab-9", "deliveries": [bad]})
    assert r.json()["results"][0]["status"] == "rejected"
    probs = client.get("/api/v1/sync/problems", headers=h["mgr"]).json()
    assert probs[0]["device_id"] == "tab-9" and probs[0]["rejected"] == 1
    assert client.get("/api/v1/sync/problems", headers=h["clerk"]).status_code == 403
