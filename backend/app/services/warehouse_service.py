"""Aggregation batches, warehouse dispatch, warehouse receipts, discrepancies and reconciliation.

Batch lifecycle:  open -> closed -> dispatched -> received -> partially_sold -> sold
Golden rule: NOTHING here modifies a farmer's delivery record. Differences between
stages are recorded as discrepancies with an explanation and a responsible user.
"""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.database.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models import (
    AggregationBatch, AuctionLot, BatchDelivery, CollectionCentre, Crop, Delivery, Discrepancy, DispatchBatch,
    LotAllocation, Organization, Season, User, Warehouse, WarehouseDispatch, WarehouseReceipt, WarehouseReceiptLine,
)
from app.services import audit_service
from app.services.numbering import next_number
from app.services.scope import org_id, restricted_centre_ids
from app.services.settings_service import tolerance_percent

Q3 = Decimal("0.001")


def _year(db: Session, org: uuid.UUID) -> int:
    return datetime.now(ZoneInfo(db.get(Organization, org).timezone)).year


def _number(db: Session, org: uuid.UUID, kind: str, letter: str) -> str:
    code, year = db.get(Organization, org).code, _year(db, org)
    return f"{code}-{letter}{year}-{next_number(db, org, f'{kind}:{year}'):04d}"


# ------------------------------------------------------------------ batches
def _batch_options():
    return (selectinload(AggregationBatch.crop), selectinload(AggregationBatch.season),
            selectinload(AggregationBatch.centre), selectinload(AggregationBatch.creator),
            selectinload(AggregationBatch.members).selectinload(BatchDelivery.delivery).selectinload(Delivery.farmer))


def get_batch(db: Session, actor: User, batch_id: uuid.UUID) -> AggregationBatch:
    b = db.scalar(select(AggregationBatch).where(AggregationBatch.id == batch_id,
                                                 AggregationBatch.organization_id == org_id(actor))
                  .options(*_batch_options()))
    if b is None:
        raise NotFoundError("Batch not found")
    return b


def list_batches(db: Session, actor: User, *, status: str | None, crop_id, centre_id, season_id):
    stmt = select(AggregationBatch).where(AggregationBatch.organization_id == org_id(actor))
    allowed = restricted_centre_ids(actor)
    if allowed is not None:
        stmt = stmt.where(AggregationBatch.centre_id.in_(allowed))
    for col, val in ((AggregationBatch.status, status), (AggregationBatch.crop_id, crop_id),
                     (AggregationBatch.centre_id, centre_id), (AggregationBatch.season_id, season_id)):
        if val:
            stmt = stmt.where(col == val)
    return list(db.scalars(stmt.options(*_batch_options()).order_by(AggregationBatch.created_at.desc())))


def batch_delivered_weight(b: AggregationBatch) -> Decimal:
    return sum((m.net_weight for m in b.members), Decimal("0"))


def create_batch(db: Session, actor: User, crop_id, season_id, centre_id, notes: str | None) -> AggregationBatch:
    org = org_id(actor)
    for model, ident, name in ((Crop, crop_id, "Crop"), (Season, season_id, "Season"), (CollectionCentre, centre_id, "Centre")):
        obj = db.get(model, ident)
        if obj is None or obj.organization_id != org:
            raise ValidationFailedError(f"{name} not found")
    b = AggregationBatch(organization_id=org, batch_no=_number(db, org, "batch", "B"), crop_id=crop_id,
                         season_id=season_id, centre_id=centre_id, created_by=actor.id, notes=notes)
    db.add(b)
    db.flush()
    audit_service.record(db, action="batch.create", user_id=actor.id, organization_id=org, entity_type="batch",
                         entity_id=b.id, after={"batch_no": b.batch_no})
    db.commit()
    return get_batch(db, actor, b.id)


def eligible_deliveries(db: Session, actor: User, batch_id: uuid.UUID) -> list[Delivery]:
    """Recorded deliveries matching the batch's crop/season/centre that are in no batch yet."""
    b = get_batch(db, actor, batch_id)
    in_any_batch = select(BatchDelivery.delivery_id)
    return list(db.scalars(
        select(Delivery).where(Delivery.organization_id == b.organization_id, Delivery.crop_id == b.crop_id,
                               Delivery.season_id == b.season_id, Delivery.centre_id == b.centre_id,
                               Delivery.status == "recorded", Delivery.id.not_in(in_any_batch))
        .options(selectinload(Delivery.farmer)).order_by(Delivery.captured_at)))


def add_deliveries(db: Session, actor: User, batch_id: uuid.UUID, delivery_ids: list[uuid.UUID]) -> AggregationBatch:
    b = get_batch(db, actor, batch_id)
    if b.status != "open":
        raise ConflictError("Deliveries can only be added to an open batch")
    allowed = {d.id: d for d in eligible_deliveries(db, actor, batch_id)}
    bad = [str(i) for i in delivery_ids if i not in allowed]
    if bad:
        raise ValidationFailedError(
            "Some deliveries are not eligible (different crop/season/centre, voided, or already batched)")
    for i in delivery_ids:
        db.add(BatchDelivery(batch_id=b.id, delivery_id=i, net_weight=allowed[i].net_weight))
    audit_service.record(db, action="batch.add_deliveries", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="batch", entity_id=b.id, after={"delivery_ids": [str(i) for i in delivery_ids]})
    db.commit()
    db.expire(b)
    return get_batch(db, actor, b.id)


def remove_delivery(db: Session, actor: User, batch_id: uuid.UUID, delivery_id: uuid.UUID) -> AggregationBatch:
    b = get_batch(db, actor, batch_id)
    if b.status != "open":
        raise ConflictError("Deliveries can only be removed from an open batch")
    member = next((m for m in b.members if m.delivery_id == delivery_id), None)
    if member is None:
        raise NotFoundError("Delivery is not in this batch")
    b.members.remove(member)
    audit_service.record(db, action="batch.remove_delivery", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="batch", entity_id=b.id, before={"delivery_id": str(delivery_id)})
    db.commit()
    return get_batch(db, actor, b.id)


def close_batch(db: Session, actor: User, batch_id: uuid.UUID) -> AggregationBatch:
    b = get_batch(db, actor, batch_id)
    if b.status != "open":
        raise ConflictError(f"Batch is already {b.status}")
    if not b.members:
        raise ValidationFailedError("A batch needs at least one delivery")
    # Re-check every member: a delivery must not have changed since it was added.
    for m in b.members:
        if m.delivery.status != "recorded" or m.delivery.net_weight != m.net_weight:
            raise ConflictError(f"Delivery {m.delivery.receipt_no} changed after being added; remove and re-add it")
    b.status, b.total_net_weight = "closed", batch_delivered_weight(b)
    b.closed_by, b.closed_at = actor.id, datetime.now(UTC)
    audit_service.record(db, action="batch.close", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="batch", entity_id=b.id,
                         after={"deliveries": len(b.members), "total_net_weight": str(b.total_net_weight)})
    db.commit()
    return get_batch(db, actor, b.id)


# ------------------------------------------------------------------ discrepancies
def _flag(db: Session, org: uuid.UUID, batch: AggregationBatch, stage: str, expected: Decimal, actual: Decimal) -> None:
    diff = (actual - expected).quantize(Q3)
    if diff == 0:
        return
    tol = tolerance_percent(db, org)
    within = expected > 0 and abs(diff) * 100 <= expected * tol
    db.add(Discrepancy(
        organization_id=org, batch_id=batch.id, stage=stage, expected_weight=expected, actual_weight=actual,
        difference=diff, status="accepted" if within else "open",
        explanation=f"Within {tol}% tolerance (auto-accepted)" if within else None,
        resolved_at=datetime.now(UTC) if within else None))


def list_discrepancies(db: Session, actor: User, status: str | None) -> list[Discrepancy]:
    stmt = (select(Discrepancy).where(Discrepancy.organization_id == org_id(actor))
            .options(selectinload(Discrepancy.batch)).order_by(Discrepancy.created_at.desc()))
    if status:
        stmt = stmt.where(Discrepancy.status == status)
    return list(db.scalars(stmt))


def resolve_discrepancy(db: Session, actor: User, discrepancy_id: uuid.UUID, explanation: str) -> Discrepancy:
    d = db.scalar(select(Discrepancy).where(Discrepancy.id == discrepancy_id,
                                            Discrepancy.organization_id == org_id(actor))
                  .options(selectinload(Discrepancy.batch)))
    if d is None:
        raise NotFoundError("Discrepancy not found")
    if d.status != "open":
        raise ConflictError(f"Discrepancy already {d.status}")
    d.status, d.explanation, d.resolved_by, d.resolved_at = "explained", explanation, actor.id, datetime.now(UTC)
    audit_service.record(db, action="discrepancy.resolve", user_id=actor.id, organization_id=d.organization_id,
                         entity_type="discrepancy", entity_id=d.id, reason=explanation,
                         after={"batch": d.batch.batch_no, "stage": d.stage, "difference": str(d.difference)})
    db.commit()
    return d


# ------------------------------------------------------------------ dispatch
def _dispatch_options():
    return (selectinload(WarehouseDispatch.warehouse),
            selectinload(WarehouseDispatch.lines).selectinload(DispatchBatch.batch).selectinload(AggregationBatch.crop),
            selectinload(WarehouseDispatch.receipt).selectinload(WarehouseReceipt.lines))


def get_dispatch(db: Session, actor: User, dispatch_id: uuid.UUID) -> WarehouseDispatch:
    d = db.scalar(select(WarehouseDispatch).where(WarehouseDispatch.id == dispatch_id,
                                                  WarehouseDispatch.organization_id == org_id(actor))
                  .options(*_dispatch_options()))
    if d is None:
        raise NotFoundError("Dispatch not found")
    return d


def list_dispatches(db: Session, actor: User, status: str | None) -> list[WarehouseDispatch]:
    stmt = (select(WarehouseDispatch).where(WarehouseDispatch.organization_id == org_id(actor))
            .options(*_dispatch_options()).order_by(WarehouseDispatch.dispatch_date.desc(), WarehouseDispatch.created_at.desc()))
    if status:
        stmt = stmt.where(WarehouseDispatch.status == status)
    return list(db.scalars(stmt))


def create_dispatch(db: Session, actor: User, warehouse_id: uuid.UUID, dispatch_date: date, vehicle_reg: str | None,
                    driver_name: str | None, notes: str | None, lines: list[tuple[uuid.UUID, Decimal]]) -> WarehouseDispatch:
    org = org_id(actor)
    wh = db.get(Warehouse, warehouse_id)
    if wh is None or wh.organization_id != org or not wh.is_active:
        raise ValidationFailedError("Warehouse not found or inactive")
    if not lines or len({b for b, _ in lines}) != len(lines):
        raise ValidationFailedError("Select each batch once")
    batches = [get_batch(db, actor, batch_id) for batch_id, _ in lines]  # validate all first
    for b in batches:
        if b.status != "closed":
            raise ConflictError(f"Batch {b.batch_no} is {b.status}; only closed batches can be dispatched")
    d = WarehouseDispatch(organization_id=org, dispatch_no=_number(db, org, "dispatch", "D"), warehouse_id=wh.id,
                          dispatch_date=dispatch_date, vehicle_reg=vehicle_reg, driver_name=driver_name,
                          created_by=actor.id, notes=notes)
    db.add(d)
    db.flush()
    for b, (_, weight) in zip(batches, lines, strict=True):
        weight = weight.quantize(Q3)
        d.lines.append(DispatchBatch(batch_id=b.id, dispatched_weight=weight))
        b.status = "dispatched"
        _flag(db, org, b, "batch_to_dispatch", b.total_net_weight, weight)
    audit_service.record(db, action="dispatch.create", user_id=actor.id, organization_id=org, entity_type="dispatch",
                         entity_id=d.id, after={"dispatch_no": d.dispatch_no, "warehouse": wh.code,
                                                "lines": [{"batch_id": str(b), "kg": str(w)} for b, w in lines]})
    db.commit()
    return get_dispatch(db, actor, d.id)


# ------------------------------------------------------------------ warehouse receipt
def record_receipt(db: Session, actor: User, dispatch_id: uuid.UUID, receipt_no: str, receipt_date: date,
                   notes: str | None, lines: list[dict]) -> WarehouseDispatch:
    d = get_dispatch(db, actor, dispatch_id)
    if d.receipt is not None:
        raise ConflictError("A warehouse receipt was already recorded for this dispatch")
    if receipt_date < d.dispatch_date:
        raise ValidationFailedError("Receipt date cannot be before the dispatch date")
    by_batch = {l.batch_id: l for l in d.lines}
    if {l["batch_id"] for l in lines} != set(by_batch) or len(lines) != len(by_batch):
        raise ValidationFailedError("Enter received quantities for every batch on the dispatch, once each")
    if db.scalar(select(WarehouseReceipt.id).where(WarehouseReceipt.warehouse_id == d.warehouse_id,
                                                   WarehouseReceipt.receipt_no == receipt_no)):
        raise ConflictError(f"Warehouse receipt {receipt_no} already exists for this warehouse")

    # Validate EVERY line before changing anything (all-or-nothing).
    parsed = []
    for l in lines:
        received = l["received_weight"].quantize(Q3)
        rejected = l.get("rejected_weight", Decimal("0")).quantize(Q3)
        damaged = l.get("damaged_weight", Decimal("0")).quantize(Q3)
        if received - rejected - damaged < 0:
            raise ValidationFailedError("Rejected + damaged cannot exceed the received weight")
        parsed.append((l, received, rejected, damaged, received - rejected - damaged))

    r = WarehouseReceipt(organization_id=d.organization_id, warehouse_id=d.warehouse_id, dispatch_id=d.id,
                         receipt_no=receipt_no, receipt_date=receipt_date, recorded_by=actor.id, notes=notes)
    db.add(r)
    for l, received, rejected, damaged, accepted in parsed:
        r.lines.append(WarehouseReceiptLine(batch_id=l["batch_id"], received_weight=received, rejected_weight=rejected,
                                            damaged_weight=damaged, accepted_weight=accepted))
        batch = by_batch[l["batch_id"]].batch
        batch.status = "received"
        _flag(db, d.organization_id, batch, "dispatch_to_warehouse", by_batch[l["batch_id"]].dispatched_weight, received)
        if rejected + damaged > 0:
            _flag(db, d.organization_id, batch, "warehouse_rejections", received, accepted)
    d.status = "received"
    db.flush()
    audit_service.record(db, action="warehouse_receipt.create", user_id=actor.id, organization_id=d.organization_id,
                         entity_type="warehouse_receipt", entity_id=r.id,
                         after={"receipt_no": receipt_no, "dispatch_no": d.dispatch_no,
                                "lines": [{k: str(v) for k, v in l.items()} for l in lines]})
    db.commit()
    db.expire(d)
    return get_dispatch(db, actor, d.id)


# ------------------------------------------------------------------ reconciliation & traceability
def reconciliation(db: Session, actor: User, batch_id: uuid.UUID) -> dict:
    """Every stage's weight for one batch, side by side."""
    b = get_batch(db, actor, batch_id)
    delivered = batch_delivered_weight(b)
    dl = db.scalar(select(DispatchBatch).where(DispatchBatch.batch_id == b.id))
    rl = db.scalar(select(WarehouseReceiptLine).where(WarehouseReceiptLine.batch_id == b.id)
                   .options(selectinload(WarehouseReceiptLine.receipt)))
    sold = db.scalar(select(func.coalesce(func.sum(AuctionLot.quantity_sold), 0)).where(AuctionLot.batch_id == b.id))
    sold_value = db.scalar(select(func.coalesce(func.sum(AuctionLot.total_value), 0)).where(AuctionLot.batch_id == b.id))
    discrepancies = list(db.scalars(select(Discrepancy).where(Discrepancy.batch_id == b.id).order_by(Discrepancy.created_at)))
    accepted = rl.accepted_weight if rl else None
    return {
        "batch": b, "farmer_deliveries": len(b.members), "delivered_weight": delivered,
        "batch_weight": b.total_net_weight, "dispatched_weight": dl.dispatched_weight if dl else None,
        "received_weight": rl.received_weight if rl else None,
        "rejected_weight": rl.rejected_weight if rl else None, "damaged_weight": rl.damaged_weight if rl else None,
        "accepted_weight": accepted, "warehouse_receipt_no": rl.receipt.receipt_no if rl else None,
        "sold_weight": Decimal(sold), "sold_value": Decimal(sold_value),
        "unsold_weight": (accepted - Decimal(sold)) if accepted is not None else None,
        "discrepancies": discrepancies,
    }


def trace_delivery(db: Session, actor: User, delivery_id: uuid.UUID) -> dict:
    """Follow one farmer delivery through batch, dispatch, warehouse and auction lots."""
    from app.services.delivery_service import get_delivery  # local import avoids a cycle
    d = get_delivery(db, actor, delivery_id)
    member = db.scalar(select(BatchDelivery).where(BatchDelivery.delivery_id == d.id))
    out: dict = {"delivery_id": d.id, "receipt_no": d.receipt_no, "net_weight": d.net_weight,
                 "batch": None, "dispatch": None, "warehouse_receipt": None, "allocations": []}
    if member is None:
        return out
    b = db.get(AggregationBatch, member.batch_id)
    out["batch"] = {"id": b.id, "batch_no": b.batch_no, "status": b.status, "total_net_weight": b.total_net_weight}
    dl = db.scalar(select(DispatchBatch).where(DispatchBatch.batch_id == b.id))
    if dl:
        disp = db.get(WarehouseDispatch, dl.dispatch_id)
        out["dispatch"] = {"id": disp.id, "dispatch_no": disp.dispatch_no, "dispatch_date": disp.dispatch_date,
                           "dispatched_weight": dl.dispatched_weight}
    rl = db.scalar(select(WarehouseReceiptLine).where(WarehouseReceiptLine.batch_id == b.id)
                   .options(selectinload(WarehouseReceiptLine.receipt)))
    if rl:
        out["warehouse_receipt"] = {"receipt_no": rl.receipt.receipt_no, "receipt_date": rl.receipt.receipt_date,
                                    "received_weight": rl.received_weight, "accepted_weight": rl.accepted_weight}
    allocs = db.scalars(select(LotAllocation).where(LotAllocation.delivery_id == d.id)
                        .options(selectinload(LotAllocation.lot).selectinload(AuctionLot.auction)))
    out["allocations"] = [{"auction_ref": a.lot.auction.auction_ref, "auction_date": a.lot.auction.auction_date,
                           "lot_no": a.lot.lot_no, "price_per_kg": a.price_per_kg, "weight_shared": a.weight_shared,
                           "weight_absorbed": a.weight_absorbed} for a in allocs]
    return out


def delivery_batch_id(db: Session, delivery_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(BatchDelivery.batch_id).where(BatchDelivery.delivery_id == delivery_id))


# ------------------------------------------------------------------ warehouses (registry)
def list_warehouses(db: Session, actor: User) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).where(Warehouse.organization_id == org_id(actor)).order_by(Warehouse.name)))


def create_warehouse(db: Session, actor: User, data: dict) -> Warehouse:
    org = org_id(actor)
    data["code"] = data["code"].upper()
    if db.scalar(select(Warehouse.id).where(Warehouse.organization_id == org, Warehouse.code == data["code"])):
        raise ConflictError(f"Warehouse code {data['code']} already exists")
    w = Warehouse(organization_id=org, **data)
    db.add(w)
    db.flush()
    audit_service.record(db, action="warehouse.create", user_id=actor.id, organization_id=org,
                         entity_type="warehouse", entity_id=w.id, after={"code": w.code, "name": w.name})
    db.commit()
    return w
