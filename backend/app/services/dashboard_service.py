"""Dashboard metrics. Every figure is a SQL aggregate over real records — no demo numbers.

Filters (all optional): date range on delivery capture time, crop, collection centre.
Financial figures are only returned to users with payout.view.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    AggregationBatch, Auction, AuctionLot, BatchDelivery, CollectionCentre, Crop, DeductionType, Delivery,
    DeliveryAmendment, Discrepancy, Farmer, FarmerPayout, Organization, Payment, PaymentBatch, PayoutLine, PayoutRun,
    SmsMessage, SyncLog, User,
)
from app.services.scope import org_id, restricted_centre_ids

D0 = Decimal("0")


def _num(v) -> Decimal:
    return Decimal(v or 0)


def dashboard(db: Session, actor: User, *, date_from: datetime | None, date_to: datetime | None,
              crop_id: uuid.UUID | None, centre_id: uuid.UUID | None) -> dict:
    org = org_id(actor)
    tz = db.get(Organization, org).timezone
    allowed = restricted_centre_ids(actor)

    # ---- delivery filter shared by most queries
    conds = [Delivery.organization_id == org, Delivery.status == "recorded"]
    if date_from:
        conds.append(Delivery.captured_at >= date_from)
    if date_to:
        conds.append(Delivery.captured_at < date_to)
    if crop_id:
        conds.append(Delivery.crop_id == crop_id)
    if centre_id:
        conds.append(Delivery.centre_id == centre_id)
    if allowed is not None:
        conds.append(Delivery.centre_id.in_(allowed))
    where = and_(*conds)

    total_deliveries, total_kg = db.execute(select(func.count(), func.coalesce(func.sum(Delivery.net_weight), 0)).where(where)).one()

    # Produce position along the chain (by batch status of each delivery)
    stage = db.execute(
        select(func.coalesce(AggregationBatch.status, "unbatched"), func.coalesce(func.sum(Delivery.net_weight), 0))
        .select_from(Delivery).outerjoin(BatchDelivery, BatchDelivery.delivery_id == Delivery.id)
        .outerjoin(AggregationBatch, AggregationBatch.id == BatchDelivery.batch_id)
        .where(where).group_by(AggregationBatch.status)).all()
    by_stage = {s: _num(kg) for s, kg in stage}
    awaiting_dispatch = by_stage.get("unbatched", D0) + by_stage.get("open", D0) + by_stage.get("closed", D0)
    at_warehouse = sum((by_stage.get(s, D0) for s in ("dispatched", "received", "partially_sold", "sold")), D0)

    local_day = cast(func.timezone(tz, Delivery.captured_at), Date)
    daily = db.execute(select(local_day, func.count(), func.sum(Delivery.net_weight)).where(where)
                       .group_by(local_day).order_by(local_day)).all()
    month = func.to_char(func.timezone(tz, Delivery.captured_at), "YYYY-MM")
    monthly = db.execute(select(month, func.count(), func.count(func.distinct(Delivery.farmer_id)), func.sum(Delivery.net_weight))
                         .where(where).group_by(month).order_by(month)).all()
    by_crop = db.execute(select(Crop.name, func.sum(Delivery.net_weight), func.count()).join(Crop, Crop.id == Delivery.crop_id)
                         .where(where).group_by(Crop.name).order_by(func.sum(Delivery.net_weight).desc())).all()
    by_centre = db.execute(select(CollectionCentre.name, func.sum(Delivery.net_weight), func.count(),
                                  func.count(func.distinct(Delivery.farmer_id)))
                           .join(CollectionCentre, CollectionCentre.id == Delivery.centre_id)
                           .where(where).group_by(CollectionCentre.name).order_by(func.sum(Delivery.net_weight).desc())).all()

    farmers_total = db.scalar(select(func.count()).select_from(Farmer).where(Farmer.organization_id == org))
    farmers_active = db.scalar(select(func.count()).select_from(Farmer).where(Farmer.organization_id == org, Farmer.status == "active"))
    centres = db.scalar(select(func.count()).select_from(CollectionCentre).where(
        CollectionCentre.organization_id == org, CollectionCentre.status == "active"))

    recent = db.execute(select(Delivery.id, Delivery.receipt_no, Delivery.captured_at, Delivery.net_weight, Farmer.full_name,
                               Crop.name, CollectionCentre.name)
                        .join(Farmer, Farmer.id == Delivery.farmer_id).join(Crop, Crop.id == Delivery.crop_id)
                        .join(CollectionCentre, CollectionCentre.id == Delivery.centre_id)
                        .where(where).order_by(Delivery.captured_at.desc()).limit(8)).all()

    out: dict = {
        "farmers_total": farmers_total, "farmers_active": farmers_active, "centres_active": centres,
        "deliveries": total_deliveries, "collected_kg": _num(total_kg),
        "awaiting_dispatch_kg": awaiting_dispatch, "at_warehouse_kg": at_warehouse,
        "daily": [{"date": str(d), "deliveries": n, "kg": _num(kg)} for d, n, kg in daily],
        "monthly": [{"month": m, "deliveries": n, "farmers": f, "kg": _num(kg)} for m, n, f, kg in monthly],
        "by_crop": [{"name": n, "kg": _num(kg), "deliveries": c} for n, kg, c in by_crop],
        "by_centre": [{"name": n, "kg": _num(kg), "deliveries": c, "farmers": f} for n, kg, c, f in by_centre],
        "recent_deliveries": [{"id": i, "receipt_no": r, "captured_at": t, "net_weight": kg, "farmer": fn, "crop": cn,
                               "centre": ce} for i, r, t, kg, fn, cn, ce in recent],
        "tasks": _tasks(db, actor, org),
        "finance": None,
    }

    if "payout.view" in actor.permission_codes:
        auc_conds = [Auction.organization_id == org, Auction.status == "approved"]
        if crop_id:
            auc_conds.append(Auction.crop_id == crop_id)
        if date_from:
            auc_conds.append(Auction.auction_date >= date_from.date())
        if date_to:
            auc_conds.append(Auction.auction_date < date_to.date())
        sold_kg, sold_value = db.execute(select(func.coalesce(func.sum(AuctionLot.quantity_sold), 0),
                                                func.coalesce(func.sum(AuctionLot.total_value), 0))
                                         .join(Auction).where(*auc_conds)).one()
        auctions = db.execute(select(Auction.auction_ref, Auction.auction_date, func.sum(AuctionLot.quantity_sold),
                                     func.sum(AuctionLot.total_value))
                              .join(AuctionLot).where(*auc_conds).group_by(Auction.id).order_by(Auction.auction_date)).all()

        run_conds = [PayoutRun.organization_id == org, PayoutRun.status == "approved"]
        if crop_id:
            run_conds.append(PayoutRun.crop_id == crop_id)
        calculated = db.scalar(select(func.coalesce(func.sum(FarmerPayout.net_payable), 0)).join(PayoutRun)
                               .where(*run_conds, FarmerPayout.status.in_(("approved", "paid"))))
        deductions = db.scalar(select(func.coalesce(func.sum(FarmerPayout.total_deductions), 0)).join(PayoutRun).where(*run_conds))
        paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(FarmerPayout, FarmerPayout.id == Payment.farmer_payout_id)
                         .join(PayoutRun).where(*run_conds, Payment.status == "paid"))
        in_process = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(FarmerPayout, FarmerPayout.id == Payment.farmer_payout_id)
                               .join(PayoutRun).where(*run_conds, Payment.status.in_(("pending", "exported"))))
        breakdown = db.execute(select(PayoutLine.line_type, func.coalesce(DeductionType.name, "Input loan repayments"),
                                      func.sum(PayoutLine.amount))
                               .join(FarmerPayout).join(PayoutRun).outerjoin(DeductionType, DeductionType.id == PayoutLine.deduction_type_id)
                               .where(*run_conds, PayoutLine.line_type != "earning")
                               .group_by(PayoutLine.line_type, DeductionType.name).order_by(func.sum(PayoutLine.amount).desc())).all()
        out["finance"] = {
            "sold_kg": _num(sold_kg), "auction_value": _num(sold_value),
            "avg_price": (_num(sold_value) / _num(sold_kg)).quantize(Decimal("0.01")) if sold_kg else None,
            "payouts_calculated": _num(calculated), "payments_completed": _num(paid), "payments_in_process": _num(in_process),
            "outstanding": _num(calculated) - _num(paid), "deductions": _num(deductions),
            "auctions": [{"ref": r, "date": str(d), "kg": _num(kg), "value": _num(v),
                          "avg_price": (_num(v) / _num(kg)).quantize(Decimal("0.01")) if kg else None} for r, d, kg, v in auctions],
            "deduction_breakdown": [{"type": t, "name": n, "amount": _num(a)} for t, n, a in breakdown],
        }
    return out


def _tasks(db: Session, actor: User, org: uuid.UUID) -> list[dict]:
    """Things waiting for someone — shown only when the user can act on them."""
    perms = actor.permission_codes
    checks = [
        ("delivery.amend_approve", "Delivery corrections awaiting approval", "/deliveries",
         select(func.count()).select_from(DeliveryAmendment).join(Delivery)
         .where(Delivery.organization_id == org, DeliveryAmendment.status == "pending")),
        ("reconciliation.approve", "Open warehouse discrepancies", "/warehouse",
         select(func.count()).select_from(Discrepancy).where(Discrepancy.organization_id == org, Discrepancy.status == "open")),
        ("batch.manage", "Open aggregation batches", "/batches",
         select(func.count()).select_from(AggregationBatch).where(AggregationBatch.organization_id == org, AggregationBatch.status == "open")),
        ("auction.approve", "Auctions awaiting approval", "/auctions",
         select(func.count()).select_from(Auction).where(Auction.organization_id == org, Auction.status == "draft")),
        ("payout.approve", "Payout runs awaiting approval", "/payouts",
         select(func.count()).select_from(PayoutRun).where(PayoutRun.organization_id == org, PayoutRun.status == "calculated")),
        ("payment_batch.approve", "Payment batches awaiting approval", "/payments",
         select(func.count()).select_from(PaymentBatch).where(PaymentBatch.organization_id == org, PaymentBatch.status == "awaiting_approval")),
        ("payment.reconcile", "Payments exported, awaiting result", "/payments",
         select(func.count()).select_from(Payment).join(PaymentBatch).where(PaymentBatch.organization_id == org, Payment.status == "exported")),
        ("payment_batch.prepare", "Failed payments to retry", "/payments",
         select(func.count()).select_from(Payment).join(PaymentBatch).join(FarmerPayout, FarmerPayout.id == Payment.farmer_payout_id)
         .where(PaymentBatch.organization_id == org, Payment.status == "failed", FarmerPayout.status == "approved")),
        ("delivery.amend_approve", "Offline sync records with problems", "/sync-review",
         select(func.coalesce(func.sum(SyncLog.conflicts + SyncLog.rejected), 0)).where(SyncLog.organization_id == org)),
        ("notification.manage", "Failed SMS messages", "/notifications",
         select(func.count()).select_from(SmsMessage).where(SmsMessage.organization_id == org, SmsMessage.status == "failed")),
    ]
    tasks = []
    for perm, label, link, stmt in checks:
        if perm in perms:
            n = db.scalar(stmt) or 0
            if n:
                tasks.append({"label": label, "count": int(n), "link": link})
    return tasks
