"""End-to-end finance: deductions, loans, payout runs (both loss policies), payments.

Continues the Phase 6 worked example (farmers A 400 kg, B 350 kg, C 250 kg; lots
L1 600 kg @ 2,100 and L2 380 kg @ 1,950). Deductions (example rates only):
  District levy 3% of gross (priority 10), Cooperative levy 25/kg (20), Transport 5,000 fixed (30).
Farmer A has input loan 150,000 with a 50% cap.

FARMER A — loss SHARED:  240 kg x 2,100 + 152 kg x 1,950 = 504,000 + 296,400 = 800,400.00
   levies 24,012.00 + 9,800.00 + 5,000.00 = 38,812.00 ; available 761,588.00
   loan min(150,000 ; 50% of 761,588 = 380,794) = 150,000.00
   NET = 611,588.00
FARMER A — loss ABSORBED (AMCOS bears the 20 kg): gross 816,734.70 ; NET 627,232.66 (see test_payout_engine)
"""
import uuid
from datetime import date
from decimal import Decimal as D

from sqlalchemy import select

from app.models import Farmer, InputLoan, LoanRepayment
from tests.test_warehouse_auction import new_batch, world  # noqa: F401  (fixture re-use)


def sell_everything(client, w):
    """Run the Phase 6 chain: deliveries -> batch -> dispatch -> receipt -> approved auction."""
    h = w["h"]
    ids = [w["deliver"](f, kg) for f, kg in zip(w["farmers"], ["400", "350", "250"])]
    b = new_batch(client, w)
    client.post(f"/api/v1/batches/{b}/deliveries", headers=h["wh"], json={"delivery_ids": ids})
    client.post(f"/api/v1/batches/{b}/close", headers=h["wh"])
    disp = client.post("/api/v1/dispatches", headers=h["wh"], json={
        "warehouse_id": str(w["warehouse"].id), "dispatch_date": str(date.today()),
        "lines": [{"batch_id": b, "dispatched_weight": "998"}]}).json()
    client.post(f"/api/v1/dispatches/{disp['id']}/receipt", headers=h["wh"], json={
        "receipt_no": "WR-1", "receipt_date": str(date.today()),
        "lines": [{"batch_id": b, "received_weight": "990", "rejected_weight": "10"}]})
    a = client.post("/api/v1/auctions", headers=h["mgr"], json={
        "auction_ref": "AUC-1", "auction_date": str(date.today()), "crop_id": str(w["crop"].id),
        "season_id": str(w["season"].id)}).json()
    for lot_no, qty, price in (("L1", "600", "2100"), ("L2", "380", "1950")):
        client.post(f"/api/v1/auctions/{a['id']}/lots", headers=h["mgr"], json={
            "batch_id": b, "lot_no": lot_no, "quantity_sold": qty, "price_per_kg": price})
    assert client.post(f"/api/v1/auctions/{a['id']}/approve", headers=h["mgr2"]).status_code == 200


def test_payouts_and_payments_end_to_end(client, world, db, make_user, login):  # noqa: F811
    w, h = world, world["h"]
    make_user("accountant")
    h["acc"] = login("accountant@test.amcos")
    A, B, C = w["farmers"]
    A.mobile_money_number, B.mobile_money_number = "+255700000001", "+255700000002"  # C has none
    db.flush()

    for code, name, method, rate, prio in (("DLEVY", "District levy", "percent_of_gross", "3", 10),
                                           ("COOP", "Cooperative levy", "per_kg", "25", 20),
                                           ("TRANS", "Transport", "fixed", "5000", 30)):
        r = client.post("/api/v1/deductions", headers=h["acc"], json={
            "code": code, "name": name, "calc_method": method, "rate": rate, "priority": prio,
            "category": "other" if code == "TRANS" else "levy", "effective_from": "2026-01-01"})
        assert r.status_code == 201, r.text
    loan = client.post("/api/v1/loans", headers=h["acc"], json={
        "farmer_id": str(A.id), "issue_date": "2026-10-15", "description": "Sulphur dust 6 bags",
        "principal": "150000", "max_deduction_percent": "50"})
    assert loan.status_code == 201, loan.text

    # Nothing sold yet -> cannot calculate
    body = {"crop_id": str(w["crop"].id), "season_id": str(w["season"].id), "loss_policy": "shared"}
    assert client.post("/api/v1/payout-runs", headers=h["acc"], json=body).status_code == 422

    sell_everything(client, w)

    # --- SHARED policy
    run = client.post("/api/v1/payout-runs", headers=h["acc"], json=body)
    assert run.status_code == 201, run.text
    run = run.json()
    pa = next(p for p in run["payouts"] if p["farmer"]["id"] == str(A.id))
    assert (pa["eligible_weight"], pa["gross_amount"], pa["net_payable"]) == ("392.000", "800400.00", "611588.00")
    lines = {l["description"].split(" (")[0]: l["amount"] for l in pa["lines"]}
    assert lines["District levy"] == "24012.00" and lines["Cooperative levy"] == "9800.00" and lines["Transport"] == "5000.00"
    assert any(l["line_type"] == "loan" and l["amount"] == "150000.00" for l in pa["lines"])
    assert D(run["total_gross"]) == sum(D(p["gross_amount"]) for p in run["payouts"])
    # Sold kg can't be in two live runs at once
    assert client.post("/api/v1/payout-runs", headers=h["acc"], json=body).status_code == 422

    # --- Switch to ABSORBED: cancel (reason required) and recalculate
    assert client.post(f"/api/v1/payout-runs/{run['id']}/cancel", headers=h["acc"], json={"reason": "no"}).status_code == 422
    assert client.post(f"/api/v1/payout-runs/{run['id']}/cancel", headers=h["acc"],
                       json={"reason": "Board resolved AMCOS absorbs warehouse loss"}).status_code == 200
    run2 = client.post("/api/v1/payout-runs", headers=h["acc"], json=body | {"loss_policy": "absorbed"}).json()
    pa2 = next(p for p in run2["payouts"] if p["farmer"]["id"] == str(A.id))
    assert (pa2["eligible_weight"], pa2["gross_amount"], pa2["net_payable"]) == ("400.000", "816734.70", "627232.66")

    # --- Approval: accountant can't approve; manager can (and is a different user)
    assert client.post(f"/api/v1/payout-runs/{run2['id']}/approve", headers=h["acc"]).status_code == 403
    ok = client.post(f"/api/v1/payout-runs/{run2['id']}/approve", headers=h["mgr"])
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    # loan repayment booked on approval
    loan_obj = db.scalar(select(InputLoan).where(InputLoan.farmer_id == A.id))
    db.refresh(loan_obj)
    assert loan_obj.outstanding == D("0") and loan_obj.status == "repaid"
    assert db.scalar(select(LoanRepayment).where(LoanRepayment.loan_id == loan_obj.id)).source == "payout"

    # --- Payments
    elig = client.get("/api/v1/payment-batches/eligible?method=mobile_money", headers=h["acc"]).json()
    by_farmer = {e["farmer"]["id"]: e for e in elig}
    assert by_farmer[str(C.id)]["problem"] == "missing mobile money number"
    bad = client.post("/api/v1/payment-batches", headers=h["acc"], json={
        "method": "mobile_money", "payout_ids": [by_farmer[str(C.id)]["payout_id"]]})
    assert bad.status_code == 422
    ids = [by_farmer[str(A.id)]["payout_id"], by_farmer[str(B.id)]["payout_id"]]
    batch = client.post("/api/v1/payment-batches", headers=h["acc"], json={"method": "mobile_money", "payout_ids": ids})
    assert batch.status_code == 201, batch.text
    batch = batch.json()
    # duplicate prevention: same payouts can't go in a second batch
    assert client.post("/api/v1/payment-batches", headers=h["acc"],
                       json={"method": "mobile_money", "payout_ids": ids}).status_code == 422

    url = f"/api/v1/payment-batches/{batch['id']}"
    assert client.post(f"{url}/export", headers=h["acc"]).status_code == 409          # not approved yet
    assert client.post(f"{url}/submit", headers=h["acc"]).json()["status"] == "awaiting_approval"
    assert client.post(f"{url}/approve", headers=h["acc"]).status_code == 403        # preparer lacks permission
    assert client.post(f"{url}/approve", headers=h["mgr"]).json()["status"] == "approved"

    exp = client.post(f"{url}/export?format=csv", headers=h["acc"])
    assert exp.status_code == 200 and "text/csv" in exp.headers["content-type"]
    csv_text = exp.content.decode("utf-8-sig")
    assert "627232.66" in csv_text and "+255700000001" in csv_text
    after = client.get(url, headers=h["acc"]).json()
    assert after["status"] == "exported"
    assert {p["status"] for p in after["payments"]} == {"exported"}   # exported is NOT paid
    xlsx = client.post(f"{url}/export?format=xlsx", headers=h["acc"])
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"      # xlsx is a zip file

    pay_a = next(p for p in after["payments"] if p["farmer"]["id"] == str(A.id))
    pay_b = next(p for p in after["payments"] if p["farmer"]["id"] == str(B.id))
    assert client.post(f"{url}/results", headers=h["acc"], json={"results": [
        {"payment_id": pay_a["id"], "status": "paid"}]}).status_code == 422                 # needs a transaction ref
    res = client.post(f"{url}/results", headers=h["acc"], json={"results": [
        {"payment_id": pay_a["id"], "status": "paid", "transaction_ref": "MP261123.1001.A1"},
        {"payment_id": pay_b["id"], "status": "failed", "failure_reason": "Recipient wallet not registered"}]})
    assert res.status_code == 200 and res.json()["status"] == "partially_completed"

    # Failed payout can be retried in a new batch; the paid one cannot
    elig2 = {e["farmer"]["id"]: e for e in client.get("/api/v1/payment-batches/eligible?method=mobile_money", headers=h["acc"]).json()}
    assert str(B.id) in elig2 and str(A.id) not in elig2

    # Statement explains everything
    st = client.get(f"/api/v1/farmers/{A.id}/statement", headers=h["acc"]).json()
    t = st["totals"]
    assert (t["gross"], t["loan_deductions"], t["net_payable"], t["paid"], t["unpaid"]) == \
        ("816734.70", "150000.00", "627232.66", "627232.66", "0.00")
    assert t["levies"] == str(D("24502.04") + D("10000.00")) and t["other_deductions"] == "5000.00"

    # Reversal re-opens the payout for payment
    rev = client.post(f"{url}/payments/{pay_a['id']}/reverse", headers=h["mgr"], json={"reason": "Sent to wrong wallet, recovered"})
    assert rev.status_code == 200
    elig3 = {e["farmer"]["id"] for e in client.get("/api/v1/payment-batches/eligible?method=mobile_money", headers=h["acc"]).json()}
    assert str(A.id) in elig3


def test_finance_permissions(client, world):  # noqa: F811
    h = world["h"]
    # clerk and warehouse officer cannot see or configure money
    assert client.get("/api/v1/payout-runs", headers=h["clerk"]).status_code == 403
    assert client.post("/api/v1/deductions", headers=h["wh"], json={
        "code": "X", "name": "Xx", "calc_method": "fixed", "rate": "1", "effective_from": "2026-01-01"}).status_code == 403
    assert client.get(f"/api/v1/farmers/{world['farmers'][0].id}/statement", headers=h["clerk"]).status_code == 403
    # invalid percentage rejected by validation
    assert client.post("/api/v1/deductions", headers=h["mgr"], json={
        "code": "P", "name": "Pp", "calc_method": "percent_of_gross", "rate": "150", "effective_from": "2026-01-01"}).status_code == 422


def test_cash_repayment_cannot_exceed_balance(client, world, make_user, login):  # noqa: F811
    make_user("accountant")
    acc = login("accountant@test.amcos")
    farmer = world["farmers"][0]
    loan = client.post("/api/v1/loans", headers=acc, json={
        "farmer_id": str(farmer.id), "issue_date": "2026-10-01", "description": "Pesticide", "principal": "10000"}).json()
    url = f"/api/v1/loans/{loan['id']}/repayments"
    assert client.post(url, headers=acc, json={"amount": "12000", "repayment_date": "2026-11-01"}).status_code == 422
    r = client.post(url, headers=acc, json={"amount": "10000", "repayment_date": "2026-11-01", "reference": "RCPT-9"}).json()
    assert r["outstanding"] == "0.00" and r["status"] == "repaid"
