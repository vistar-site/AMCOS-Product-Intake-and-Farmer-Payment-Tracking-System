"""End-to-end: deliveries -> batch -> dispatch -> warehouse -> auction -> allocations.

WORKED EXAMPLE (all numbers checked by hand):

  Farmer A delivers 400 kg, B 350 kg, C 250 kg          -> batch total 1,000.000 kg
  Dispatched (weighed at loading)          998.000 kg   -> -2 kg  (0.2%, within 0.5% tolerance: auto-accepted)
  Received at warehouse                    990.000 kg   -> -8 kg  (0.8%: OPEN discrepancy)
  Rejected at warehouse                     10.000 kg   -> accepted 980.000 kg
  Auction: lot L1 600 kg @ 2,100 TZS/kg = 1,260,000.00
           lot L2 380 kg @ 1,950 TZS/kg =   741,000.00      (980 kg sold -> batch "sold")

  SHARED policy (loss shared pro rata):  A = 40%, B = 35%, C = 25% of every lot
     L1: A 240.000  B 210.000  C 150.000      L2: A 152.000  B 133.000  C 95.000
     totals A 392.000  B 343.000  C 245.000  (= 980 kg, the quantity actually sold)

  ABSORBED policy (AMCOS bears the 20 kg loss): lot weights grossed up by 1000/980
     L1 target 612.245 kg -> A 244.898  B 214.286  C 153.061
     L2 target 387.755 kg -> A 155.102  B 135.714  C  96.939
     totals A 400.000  B 350.000  C 250.000  (= each farmer's full delivery)
"""
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import CollectionCentre, Crop, Farmer, Season, Warehouse


@pytest.fixture
def world(db, org, make_user, login, client):
    centre = db.scalar(select(CollectionCentre).where(CollectionCentre.organization_id == org.id))
    today = date.today()
    season = Season(organization_id=org.id, name="S", start_date=today - timedelta(days=90), end_date=today + timedelta(days=90))
    crop = Crop(organization_id=org.id, code="CASHEW", name="Cashew")
    other_crop = Crop(organization_id=org.id, code="SESAME", name="Sesame")
    warehouse = Warehouse(organization_id=org.id, code="WH1", name="Warehouse One")
    farmers = [Farmer(organization_id=org.id, membership_no=f"F-{n}", full_name=f"Farmer {n}") for n in "ABC"]
    db.add_all([season, crop, other_crop, warehouse, *farmers])
    db.flush()
    make_user("manager")
    make_user("manager", email="manager2@test.amcos")
    make_user("warehouse_officer")
    make_user("clerk")
    h = {"mgr": login("manager@test.amcos"), "mgr2": login("manager2@test.amcos"),
         "wh": login("warehouse_officer@test.amcos"), "clerk": login("clerk@test.amcos")}

    def deliver(farmer, kg, crop_id=None):
        r = client.post("/api/v1/deliveries", headers=h["mgr"], json={
            "id": str(uuid.uuid4()), "farmer_id": str(farmer.id), "centre_id": str(centre.id),
            "crop_id": str(crop_id or crop.id), "gross_weight": kg, "captured_at": datetime.now(UTC).isoformat()})
        assert r.status_code == 201, r.text
        return r.json()["delivery"]["id"]

    return {"centre": centre, "season": season, "crop": crop, "other_crop": other_crop, "warehouse": warehouse,
            "farmers": farmers, "h": h, "deliver": deliver}


def new_batch(client, w, headers=None):
    r = client.post("/api/v1/batches", headers=headers or w["h"]["wh"], json={
        "crop_id": str(w["crop"].id), "season_id": str(w["season"].id), "centre_id": str(w["centre"].id)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_full_chain_worked_example(client, world):
    w, h = world, world["h"]
    ids = [w["deliver"](f, kg) for f, kg in zip(w["farmers"], ["400", "350", "250"])]
    batch = new_batch(client, w)

    eligible = client.get(f"/api/v1/batches/{batch}/eligible-deliveries", headers=h["wh"]).json()
    assert {d["id"] for d in eligible} == set(ids)
    assert client.post(f"/api/v1/batches/{batch}/deliveries", headers=h["wh"], json={"delivery_ids": ids}).status_code == 200
    closed = client.post(f"/api/v1/batches/{batch}/close", headers=h["wh"]).json()
    assert closed["status"] == "closed" and closed["total_net_weight"] == "1000.000"

    d = client.post("/api/v1/dispatches", headers=h["wh"], json={
        "warehouse_id": str(w["warehouse"].id), "dispatch_date": str(date.today()), "vehicle_reg": "T 123 ABC",
        "lines": [{"batch_id": batch, "dispatched_weight": "998"}]})
    assert d.status_code == 201, d.text
    dispatch = d.json()
    assert dispatch["dispatch_no"].startswith("TST-D")

    r = client.post(f"/api/v1/dispatches/{dispatch['id']}/receipt", headers=h["wh"], json={
        "receipt_no": "WR-55501", "receipt_date": str(date.today()),
        "lines": [{"batch_id": batch, "received_weight": "990", "rejected_weight": "10"}]})
    assert r.status_code == 201, r.text
    assert r.json()["receipt"]["lines"][0]["accepted_weight"] == "980.000"

    rec = client.get(f"/api/v1/batches/{batch}/reconciliation", headers=h["mgr"]).json()
    assert (rec["delivered_weight"], rec["dispatched_weight"], rec["received_weight"], rec["accepted_weight"]) == \
        ("1000.000", "998.000", "990.000", "980.000")
    by_stage = {x["stage"]: x for x in rec["discrepancies"]}
    assert by_stage["batch_to_dispatch"]["status"] == "accepted"            # -2 kg, within tolerance
    assert by_stage["dispatch_to_warehouse"]["status"] == "open"            # -8 kg
    assert by_stage["dispatch_to_warehouse"]["difference"] == "-8.000"
    assert by_stage["warehouse_rejections"]["difference"] == "-10.000"

    # Original farmer deliveries are untouched by any of this
    for i, kg in zip(ids, ["400.000", "350.000", "250.000"]):
        assert client.get(f"/api/v1/deliveries/{i}", headers=h["mgr"]).json()["net_weight"] == kg

    # Auction entered by manager 1
    a = client.post("/api/v1/auctions", headers=h["mgr"], json={
        "auction_ref": "AUC-2026-07", "auction_date": str(date.today()), "venue": "Mtwara",
        "crop_id": str(w["crop"].id), "season_id": str(w["season"].id)}).json()
    sellable = client.get(f"/api/v1/auctions/sellable-batches?crop_id={w['crop'].id}", headers=h["mgr"]).json()
    assert sellable[0]["available_weight"] == "980.000"
    for lot_no, qty, price in (("L1", "600", "2100"), ("L2", "380", "1950")):
        r = client.post(f"/api/v1/auctions/{a['id']}/lots", headers=h["mgr"], json={
            "batch_id": batch, "lot_no": lot_no, "quantity_sold": qty, "price_per_kg": price})
        assert r.status_code == 201, r.text
    lots = {l["lot_no"]: l for l in r.json()["lots"]}
    assert lots["L1"]["total_value"] == "1260000.00" and lots["L2"]["total_value"] == "741000.00"

    # Selling more than remains is refused
    over = client.post(f"/api/v1/auctions/{a['id']}/lots", headers=h["mgr"], json={
        "batch_id": batch, "lot_no": "L3", "quantity_sold": "1", "price_per_kg": "2000"})
    assert over.status_code == 422

    # Maker-checker: creator cannot approve; second manager can
    assert client.post(f"/api/v1/auctions/{a['id']}/approve", headers=h["mgr"]).status_code == 403
    approved = client.post(f"/api/v1/auctions/{a['id']}/approve", headers=h["mgr2"])
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert client.get(f"/api/v1/batches/{batch}", headers=h["mgr"]).json()["status"] == "sold"

    # Allocations, both policies, exactly as in the worked example
    expected = {
        "L1": {"400.000": ("240.000", "244.898"), "350.000": ("210.000", "214.286"), "250.000": ("150.000", "153.061")},
        "L2": {"400.000": ("152.000", "155.102"), "350.000": ("133.000", "135.714"), "250.000": ("95.000", "96.939")},
    }
    net_of = {i: kg for i, kg in zip(ids, ["400.000", "350.000", "250.000"])}
    for lot_no, lot in lots.items():
        rows = client.get(f"/api/v1/auctions/{a['id']}/lots/{lot['id']}/allocations", headers=h["mgr"]).json()
        assert len(rows) == 3
        for row in rows:
            assert (row["weight_shared"], row["weight_absorbed"]) == expected[lot_no][net_of[row["delivery_id"]]]
        assert sum(Decimal(r["weight_shared"]) for r in rows) == Decimal(lot["quantity_sold"])

    # Traceability from farmer A's delivery all the way to the auction
    t = client.get(f"/api/v1/deliveries/{ids[0]}/trace", headers=h["mgr"]).json()
    assert t["batch"]["batch_no"] == closed["batch_no"]
    assert t["dispatch"]["dispatch_no"] == dispatch["dispatch_no"]
    assert t["warehouse_receipt"]["receipt_no"] == "WR-55501"
    assert sorted(x["lot_no"] for x in t["allocations"]) == ["L1", "L2"]
    assert sum(Decimal(x["weight_absorbed"]) for x in t["allocations"]) == Decimal("400.000")

    # Approved auctions are frozen
    assert client.post(f"/api/v1/auctions/{a['id']}/lots", headers=h["mgr"], json={
        "batch_id": batch, "lot_no": "L9", "quantity_sold": "1", "price_per_kg": "1"}).status_code == 409


def test_delivery_cannot_join_two_batches_or_wrong_crop(client, world):
    w, h = world, world["h"]
    d1 = w["deliver"](w["farmers"][0], "100")
    sesame = w["deliver"](w["farmers"][1], "50", crop_id=w["other_crop"].id)
    b1, b2 = new_batch(client, w), new_batch(client, w)
    assert client.post(f"/api/v1/batches/{b1}/deliveries", headers=h["wh"], json={"delivery_ids": [d1]}).status_code == 200
    assert client.post(f"/api/v1/batches/{b2}/deliveries", headers=h["wh"], json={"delivery_ids": [d1]}).status_code == 422
    assert client.post(f"/api/v1/batches/{b1}/deliveries", headers=h["wh"], json={"delivery_ids": [sesame]}).status_code == 422


def test_batched_delivery_cannot_be_amended_or_voided(client, world):
    w, h = world, world["h"]
    d1 = w["deliver"](w["farmers"][0], "100")
    b = new_batch(client, w)
    client.post(f"/api/v1/batches/{b}/deliveries", headers=h["wh"], json={"delivery_ids": [d1]})
    r = client.post(f"/api/v1/deliveries/{d1}/void", headers=h["mgr"], json={"reason": "Wrong farmer selected"})
    assert r.status_code == 409 and "remove it from the batch first" in r.json()["detail"]
    # After removal from the still-open batch it can be corrected
    client.delete(f"/api/v1/batches/{b}/deliveries/{d1}", headers=h["wh"])
    assert client.post(f"/api/v1/deliveries/{d1}/void", headers=h["mgr"], json={"reason": "Wrong farmer selected"}).status_code == 200


def test_cannot_close_empty_batch_or_dispatch_open_batch(client, world):
    w, h = world, world["h"]
    b = new_batch(client, w)
    assert client.post(f"/api/v1/batches/{b}/close", headers=h["wh"]).status_code == 422
    r = client.post("/api/v1/dispatches", headers=h["wh"], json={
        "warehouse_id": str(w["warehouse"].id), "dispatch_date": str(date.today()),
        "lines": [{"batch_id": b, "dispatched_weight": "10"}]})
    assert r.status_code == 409


def test_receipt_rules(client, world):
    w, h = world, world["h"]
    d1 = w["deliver"](w["farmers"][0], "100")
    b = new_batch(client, w)
    client.post(f"/api/v1/batches/{b}/deliveries", headers=h["wh"], json={"delivery_ids": [d1]})
    client.post(f"/api/v1/batches/{b}/close", headers=h["wh"])
    disp = client.post("/api/v1/dispatches", headers=h["wh"], json={
        "warehouse_id": str(w["warehouse"].id), "dispatch_date": str(date.today()),
        "lines": [{"batch_id": b, "dispatched_weight": "100"}]}).json()
    url = f"/api/v1/dispatches/{disp['id']}/receipt"
    bad = client.post(url, headers=h["wh"], json={"receipt_no": "R1", "receipt_date": str(date.today()),
                                                  "lines": [{"batch_id": b, "received_weight": "5", "rejected_weight": "6"}]})
    assert bad.status_code == 422
    ok = {"receipt_no": "R1", "receipt_date": str(date.today()), "lines": [{"batch_id": b, "received_weight": "100"}]}
    assert client.post(url, headers=h["wh"], json=ok).status_code == 201
    assert client.post(url, headers=h["wh"], json=ok).status_code == 409   # only one receipt per dispatch
    rec = client.get(f"/api/v1/batches/{b}/reconciliation", headers=h["mgr"]).json()
    assert rec["discrepancies"] == []                                        # exact match: nothing flagged


def test_permissions(client, world):
    w, h = world, world["h"]
    # Clerk cannot create batches; warehouse officer cannot enter or approve auctions
    assert client.post("/api/v1/batches", headers=h["clerk"], json={
        "crop_id": str(w["crop"].id), "season_id": str(w["season"].id), "centre_id": str(w["centre"].id)}).status_code == 403
    assert client.post("/api/v1/auctions", headers=h["wh"], json={
        "auction_ref": "X", "auction_date": str(date.today()), "crop_id": str(w["crop"].id),
        "season_id": str(w["season"].id)}).status_code == 403


def test_discrepancy_resolution_requires_permission_and_explanation(client, world):
    w, h = world, world["h"]
    d1 = w["deliver"](w["farmers"][0], "100")
    b = new_batch(client, w)
    client.post(f"/api/v1/batches/{b}/deliveries", headers=h["wh"], json={"delivery_ids": [d1]})
    client.post(f"/api/v1/batches/{b}/close", headers=h["wh"])
    client.post("/api/v1/dispatches", headers=h["wh"], json={
        "warehouse_id": str(w["warehouse"].id), "dispatch_date": str(date.today()),
        "lines": [{"batch_id": b, "dispatched_weight": "95"}]})
    disc = client.get("/api/v1/discrepancies?status=open", headers=h["mgr"]).json()[0]
    url = f"/api/v1/discrepancies/{disc['id']}/resolve"
    assert client.post(url, headers=h["wh"], json={"explanation": "Moisture loss during drying"}).status_code == 403
    assert client.post(url, headers=h["mgr"], json={"explanation": "short"}).status_code == 422
    r = client.post(url, headers=h["mgr"], json={"explanation": "Moisture loss during drying, confirmed by re-weigh"})
    assert r.status_code == 200 and r.json()["status"] == "explained"
