"""Auctions, lots and allocation of sold quantities back to farmer deliveries.

- A lot = quantity from ONE received batch sold at ONE price (prices differ per lot/grade).
- Lots may be added/removed only while the auction is a draft.
- Approval (by someone other than the creator) freezes the auction and computes
  lot_allocations for every farmer delivery in each lot's batch, under BOTH loss
  policies, so Phase 7 can apply the policy chosen for a payout run.
"""
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.database.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.models import (
    AggregationBatch, Auction, AuctionLot, BatchDelivery, Crop, CropGrade, LotAllocation, Season, User,
    WarehouseReceiptLine,
)
from app.services import audit_service
from app.services.allocation import allocate, from_grams, scale_grams, to_grams
from app.services.scope import org_id

SELLABLE = ("received", "partially_sold")


def _options():
    return (selectinload(Auction.crop), selectinload(Auction.season),
            selectinload(Auction.lots).selectinload(AuctionLot.batch),
            selectinload(Auction.lots).selectinload(AuctionLot.grade))


def get_auction(db: Session, actor: User, auction_id: uuid.UUID) -> Auction:
    a = db.scalar(select(Auction).where(Auction.id == auction_id, Auction.organization_id == org_id(actor))
                  .options(*_options()))
    if a is None:
        raise NotFoundError("Auction not found")
    return a


def list_auctions(db: Session, actor: User, status: str | None, crop_id) -> list[Auction]:
    stmt = select(Auction).where(Auction.organization_id == org_id(actor)).options(*_options())
    if status:
        stmt = stmt.where(Auction.status == status)
    if crop_id:
        stmt = stmt.where(Auction.crop_id == crop_id)
    return list(db.scalars(stmt.order_by(Auction.auction_date.desc())))


def create_auction(db: Session, actor: User, data: dict) -> Auction:
    org = org_id(actor)
    for model, key in ((Crop, "crop_id"), (Season, "season_id")):
        obj = db.get(model, data[key])
        if obj is None or obj.organization_id != org:
            raise ValidationFailedError(f"{model.__name__} not found")
    a = Auction(organization_id=org, created_by=actor.id, **data)
    db.add(a)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Auction reference {data['auction_ref']} already exists") from exc
    audit_service.record(db, action="auction.create", user_id=actor.id, organization_id=org, entity_type="auction",
                         entity_id=a.id, after={"auction_ref": a.auction_ref, "date": str(a.auction_date)})
    db.commit()
    return get_auction(db, actor, a.id)


def available_weight(db: Session, batch_id: uuid.UUID, exclude_lot: uuid.UUID | None = None) -> Decimal:
    """Accepted warehouse weight not yet assigned to any lot (draft or approved)."""
    accepted = db.scalar(select(WarehouseReceiptLine.accepted_weight).where(WarehouseReceiptLine.batch_id == batch_id))
    if accepted is None:
        return Decimal("0")
    stmt = select(func.coalesce(func.sum(AuctionLot.quantity_sold), 0)).where(AuctionLot.batch_id == batch_id)
    if exclude_lot:
        stmt = stmt.where(AuctionLot.id != exclude_lot)
    return accepted - Decimal(db.scalar(stmt))


def sellable_batches(db: Session, actor: User, crop_id: uuid.UUID) -> list[tuple[AggregationBatch, Decimal]]:
    batches = db.scalars(select(AggregationBatch).where(
        AggregationBatch.organization_id == org_id(actor), AggregationBatch.crop_id == crop_id,
        AggregationBatch.status.in_(SELLABLE)).options(selectinload(AggregationBatch.centre))
        .order_by(AggregationBatch.batch_no))
    result = [(b, available_weight(db, b.id)) for b in batches]
    return [(b, w) for b, w in result if w > 0]


def add_lot(db: Session, actor: User, auction_id: uuid.UUID, data: dict) -> Auction:
    a = get_auction(db, actor, auction_id)
    if a.status != "draft":
        raise ConflictError("Lots can only be added to a draft auction")
    b = db.get(AggregationBatch, data["batch_id"])
    if b is None or b.organization_id != a.organization_id:
        raise ValidationFailedError("Batch not found")
    if b.crop_id != a.crop_id:
        raise ValidationFailedError("Batch crop does not match the auction crop")
    if b.status not in SELLABLE:
        raise ValidationFailedError(f"Batch {b.batch_no} is {b.status}; it must be received at the warehouse first")
    if data.get("grade_id"):
        g = db.get(CropGrade, data["grade_id"])
        if g is None or g.crop_id != a.crop_id:
            raise ValidationFailedError("Grade does not belong to this crop")
    qty = data["quantity_sold"].quantize(Decimal("0.001"))
    available = available_weight(db, b.id)
    if qty > available:
        raise ValidationFailedError(f"Only {available} kg of batch {b.batch_no} is available to sell")
    price = data["price_per_kg"].quantize(Decimal("0.0001"))
    lot = AuctionLot(auction_id=a.id, batch_id=b.id, lot_no=data["lot_no"], grade_id=data.get("grade_id"),
                     quantity_sold=qty, price_per_kg=price,
                     total_value=(qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                     buyer=data.get("buyer"))
    db.add(lot)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Lot number {data['lot_no']} already exists in this auction") from exc
    audit_service.record(db, action="auction.lot_add", user_id=actor.id, organization_id=a.organization_id,
                         entity_type="auction", entity_id=a.id,
                         after={"lot_no": lot.lot_no, "batch": b.batch_no, "qty": str(qty), "price": str(price),
                                "value": str(lot.total_value)})
    db.commit()
    db.expire(a)
    return get_auction(db, actor, a.id)


def remove_lot(db: Session, actor: User, auction_id: uuid.UUID, lot_id: uuid.UUID) -> Auction:
    a = get_auction(db, actor, auction_id)
    if a.status != "draft":
        raise ConflictError("An approved auction cannot be changed")
    lot = next((l for l in a.lots if l.id == lot_id), None)
    if lot is None:
        raise NotFoundError("Lot not found")
    a.lots.remove(lot)
    audit_service.record(db, action="auction.lot_remove", user_id=actor.id, organization_id=a.organization_id,
                         entity_type="auction", entity_id=a.id,
                         before={"lot_no": lot.lot_no, "qty": str(lot.quantity_sold), "price": str(lot.price_per_kg)})
    db.commit()
    return get_auction(db, actor, a.id)


def _allocate_lot(db: Session, lot: AuctionLot) -> None:
    members = list(db.scalars(select(BatchDelivery).where(BatchDelivery.batch_id == lot.batch_id)
                              .options(selectinload(BatchDelivery.delivery))
                              .order_by(BatchDelivery.delivery_id)))  # deterministic order
    accepted = db.scalar(select(WarehouseReceiptLine.accepted_weight).where(WarehouseReceiptLine.batch_id == lot.batch_id))
    weights = [to_grams(m.net_weight) for m in members]
    delivered_g, accepted_g, lot_g = sum(weights), to_grams(accepted), to_grams(lot.quantity_sold)
    shared = allocate(lot_g, weights)
    absorbed = allocate(scale_grams(lot_g, delivered_g, accepted_g), weights)
    for m, s, ab in zip(members, shared, absorbed, strict=True):
        db.add(LotAllocation(lot_id=lot.id, delivery_id=m.delivery_id, farmer_id=m.delivery.farmer_id,
                             weight_shared=from_grams(s), weight_absorbed=from_grams(ab), price_per_kg=lot.price_per_kg))


def approve_auction(db: Session, actor: User, auction_id: uuid.UUID) -> Auction:
    a = get_auction(db, actor, auction_id)
    if a.status != "draft":
        raise ConflictError("Auction already approved")
    if a.created_by == actor.id:
        raise PermissionDeniedError("Auction results must be approved by someone other than the person who entered them")
    if not a.lots:
        raise ValidationFailedError("Add at least one lot before approving")
    for lot in a.lots:
        if available_weight(db, lot.batch_id, exclude_lot=lot.id) < lot.quantity_sold:
            raise ConflictError(f"Lot {lot.lot_no} exceeds the remaining quantity of its batch")
        _allocate_lot(db, lot)
    a.status, a.approved_by, a.approved_at = "approved", actor.id, datetime.now(UTC)
    for batch in {lot.batch for lot in a.lots}:
        batch.status = "sold" if available_weight(db, batch.id) == 0 else "partially_sold"
    audit_service.record(db, action="auction.approve", user_id=actor.id, organization_id=a.organization_id,
                         entity_type="auction", entity_id=a.id,
                         after={"auction_ref": a.auction_ref, "lots": len(a.lots),
                                "total_kg": str(sum(l.quantity_sold for l in a.lots)),
                                "total_value": str(sum(l.total_value for l in a.lots))})
    db.commit()
    return get_auction(db, actor, a.id)


def lot_allocations(db: Session, actor: User, auction_id: uuid.UUID, lot_id: uuid.UUID) -> list[LotAllocation]:
    a = get_auction(db, actor, auction_id)
    if not any(l.id == lot_id for l in a.lots):
        raise NotFoundError("Lot not found")
    from app.models import Delivery
    return list(db.scalars(select(LotAllocation).where(LotAllocation.lot_id == lot_id)
                           .options(selectinload(LotAllocation.delivery).selectinload(Delivery.farmer))))
