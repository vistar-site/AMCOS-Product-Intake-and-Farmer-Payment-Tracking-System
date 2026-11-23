"""Produce intake: recording, idempotent sync, listing, amendments and voids.

record_delivery() is THE single entry point for creating a delivery — used by
both the online form and offline sync, so the same validation always applies.
"""
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.models import (
    CollectionCentre, Crop, CropGrade, Delivery, DeliveryAmendment, Farmer, Organization, Season, SyncLog, User,
)
from app.schemas.delivery import AmendmentRequest, DeliveryCreate, SyncItemResult
from app.services import audit_service
from app.services.numbering import delivery_receipt_no
from app.services.scope import ensure_centre_allowed, org_id, restricted_centre_ids

Q3 = Decimal("0.001")
DUPLICATE_WINDOW = timedelta(minutes=15)
MAX_FUTURE_SKEW = timedelta(minutes=10)   # device clock ahead of server
MAX_BACKDATE = timedelta(days=30)         # offline devices may sync late, but not months later


class DeliveryConflict(AppError):
    status_code, code = 409, "delivery_conflict"


def _load_options():
    return (selectinload(Delivery.farmer), selectinload(Delivery.centre), selectinload(Delivery.crop),
            selectinload(Delivery.grade), selectinload(Delivery.season), selectinload(Delivery.recorder))


def payload_hash(d: DeliveryCreate) -> str:
    """Fingerprint of the fields that define the delivery (not notes/device metadata)."""
    canonical = {
        "farmer_id": str(d.farmer_id), "centre_id": str(d.centre_id), "crop_id": str(d.crop_id),
        "grade_id": str(d.grade_id) if d.grade_id else None,
        "gross": str(d.gross_weight.quantize(Q3)), "tare": str(d.tare_weight.quantize(Q3)),
        "captured_at": d.captured_at.astimezone(UTC).replace(microsecond=0).isoformat(),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def _get(db: Session, org: uuid.UUID, delivery_id: uuid.UUID) -> Delivery | None:
    return db.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.organization_id == org)
                     .options(*_load_options()))


def _validate(db: Session, actor: User, org: uuid.UUID, d: DeliveryCreate) -> tuple[Season, Crop]:
    now = datetime.now(UTC)
    if d.captured_at > now + MAX_FUTURE_SKEW:
        raise ValidationFailedError("Delivery time is in the future — check the device clock")
    if d.captured_at < now - MAX_BACKDATE:
        raise ValidationFailedError("Delivery is older than 30 days and needs manager entry")

    farmer = db.get(Farmer, d.farmer_id)
    if farmer is None or farmer.organization_id != org:
        raise ValidationFailedError("Farmer not found")
    if farmer.status != "active":
        raise ValidationFailedError(f"Farmer {farmer.membership_no} is {farmer.status}")

    centre = db.get(CollectionCentre, d.centre_id)
    if centre is None or centre.organization_id != org:
        raise ValidationFailedError("Collection centre not found")
    if centre.status != "active":
        raise ValidationFailedError("Collection centre is inactive")
    ensure_centre_allowed(actor, centre.id)

    crop = db.get(Crop, d.crop_id)
    if crop is None or crop.organization_id != org:
        raise ValidationFailedError("Crop not found")
    if not crop.is_active:
        raise ValidationFailedError(f"{crop.name} is not currently accepted")

    if d.grade_id:
        grade = db.get(CropGrade, d.grade_id)
        if grade is None or grade.crop_id != crop.id or not grade.is_active:
            raise ValidationFailedError("Grade is not valid for this crop")
    elif crop.rules.get("grade_required"):
        raise ValidationFailedError(f"A quality grade is required for {crop.name}")

    max_gross = crop.rules.get("max_gross_kg")
    if max_gross is not None and d.gross_weight > Decimal(str(max_gross)):
        raise ValidationFailedError(f"Gross weight exceeds the {max_gross} kg limit for {crop.name}")
    max_tare = crop.rules.get("max_tare_kg")
    if max_tare is not None and d.tare_weight > Decimal(str(max_tare)):
        raise ValidationFailedError(f"Tare weight exceeds the {max_tare} kg limit for {crop.name}")

    org_tz = ZoneInfo(db.get(Organization, org).timezone)
    local_date = d.captured_at.astimezone(org_tz).date()
    if d.season_id:
        season = db.get(Season, d.season_id)
        if season is None or season.organization_id != org:
            raise ValidationFailedError("Season not found")
    else:
        season = db.scalar(select(Season).where(Season.organization_id == org, Season.is_active.is_(True),
                                                Season.start_date <= local_date, Season.end_date >= local_date))
        if season is None:
            raise ValidationFailedError(f"No active season covers {local_date}")
    if not season.is_active or not (season.start_date <= local_date <= season.end_date):
        raise ValidationFailedError(f"Delivery date {local_date} is outside season {season.name}")
    return season, crop


def _duplicate_warnings(db: Session, d: Delivery) -> list[str]:
    """Same farmer + crop + net weight within 15 minutes: likely a double entry."""
    rows = db.scalars(select(Delivery.receipt_no).where(
        Delivery.id != d.id, Delivery.farmer_id == d.farmer_id, Delivery.crop_id == d.crop_id,
        Delivery.net_weight == d.net_weight, Delivery.status == "recorded",
        Delivery.captured_at.between(d.captured_at - DUPLICATE_WINDOW, d.captured_at + DUPLICATE_WINDOW))).all()
    return [f"Possible duplicate of receipt {r} (same farmer, crop and weight within 15 minutes)" for r in rows]


def record_delivery(db: Session, actor: User, data: DeliveryCreate, source: str = "online") -> tuple[Delivery, bool, list[str]]:
    """Returns (delivery, created, warnings). Does NOT commit — the caller decides.

    Idempotency: if this id already exists with the same content we return it
    (created=False). Same id + different content raises DeliveryConflict.
    """
    org = org_id(actor)
    fingerprint = payload_hash(data)
    existing = db.get(Delivery, data.id)
    if existing is not None:
        if existing.organization_id != org or existing.payload_hash != fingerprint:
            raise DeliveryConflict(
                "A different delivery was already saved with this ID. It has not been overwritten; "
                "a manager must review it.")
        return _get(db, org, data.id), False, []

    season, crop = _validate(db, actor, org, data)
    gross, tare = data.gross_weight.quantize(Q3), data.tare_weight.quantize(Q3)
    org_obj = db.get(Organization, org)
    year = data.captured_at.astimezone(ZoneInfo(org_obj.timezone)).year
    delivery = Delivery(
        id=data.id, organization_id=org, receipt_no=delivery_receipt_no(db, org, org_obj.code, year),
        provisional_receipt_no=data.provisional_receipt_no, farmer_id=data.farmer_id, centre_id=data.centre_id,
        crop_id=crop.id, grade_id=data.grade_id, season_id=season.id, recorded_by=actor.id,
        gross_weight=gross, tare_weight=tare, net_weight=gross - tare, unit=crop.unit,
        captured_at=data.captured_at, source=source, device_id=data.device_id, payload_hash=fingerprint,
        notes=data.notes,
    )
    db.add(delivery)
    db.flush()
    warnings = _duplicate_warnings(db, delivery)
    audit_service.record(db, action="delivery.create", user_id=actor.id, organization_id=org,
                         entity_type="delivery", entity_id=delivery.id,
                         after={"receipt_no": delivery.receipt_no, "farmer_id": str(delivery.farmer_id),
                                "crop": crop.code, "gross": str(gross), "tare": str(tare),
                                "net": str(delivery.net_weight), "source": source})
    saved = _get(db, org, delivery.id)
    from app.services.notification_service import enqueue_delivery_receipt  # avoid import cycle
    enqueue_delivery_receipt(db, saved)  # queued in THIS transaction; sent after commit
    return saved, True, warnings


def create_online(db: Session, actor: User, data: DeliveryCreate):
    delivery, created, warnings = record_delivery(db, actor, data, "online")
    db.commit()
    return delivery, created, warnings


def sync(db: Session, actor: User, device_id: str, items: list[DeliveryCreate]) -> list[SyncItemResult]:
    """Process a batch from an offline device. Each record succeeds or fails ON ITS OWN:
    a SAVEPOINT per record means one bad record never blocks the others."""
    results: list[SyncItemResult] = []
    for item in items:
        item.device_id = item.device_id or device_id
        savepoint = db.begin_nested()
        try:
            delivery, created, warnings = record_delivery(db, actor, item, "offline_sync")
            savepoint.commit()
            results.append(SyncItemResult(id=item.id, status="created" if created else "duplicate",
                                          receipt_no=delivery.receipt_no, warnings=warnings))
        except DeliveryConflict as exc:
            savepoint.rollback()
            results.append(SyncItemResult(id=item.id, status="conflict", message=exc.detail))
        except AppError as exc:
            savepoint.rollback()
            results.append(SyncItemResult(id=item.id, status="rejected", message=exc.detail))
        except IntegrityError:
            # Another request inserted the same id at the same instant. Nothing was saved
            # by this attempt; the device keeps the record and its next retry reports "duplicate".
            savepoint.rollback()
            results.append(SyncItemResult(id=item.id, status="rejected",
                                          message="Submitted concurrently; will be confirmed on retry"))

    counts = {s: sum(r.status == s for r in results) for s in ("created", "duplicate", "conflict", "rejected")}
    db.add(SyncLog(organization_id=actor.organization_id, user_id=actor.id, device_id=device_id,
                   received=len(items), created=counts["created"], duplicates=counts["duplicate"],
                   conflicts=counts["conflict"], rejected=counts["rejected"],
                   details=[r.model_dump(mode="json", exclude={"warnings"}) for r in results
                            if r.status in ("conflict", "rejected")]))
    if counts["conflict"] or counts["rejected"]:
        audit_service.record(db, action="sync.problems", user_id=actor.id, organization_id=actor.organization_id,
                             entity_type="device", entity_id=device_id, after=counts)
    db.commit()
    return results


def list_deliveries(db: Session, actor: User, *, q: str | None, farmer_id, centre_id, crop_id, season_id,
                    status: str | None, date_from, date_to, mine: bool, page: int, page_size: int):
    org = org_id(actor)
    stmt = select(Delivery).where(Delivery.organization_id == org)
    allowed = restricted_centre_ids(actor)
    if allowed is not None:
        stmt = stmt.where(Delivery.centre_id.in_(allowed))
    if q:
        stmt = stmt.join(Farmer, Farmer.id == Delivery.farmer_id).where(or_(
            Delivery.receipt_no.ilike(f"%{q}%"), Delivery.provisional_receipt_no.ilike(f"%{q}%"),
            func.lower(Farmer.full_name).contains(q.lower()), Farmer.membership_no.ilike(f"{q}%")))
    for col, val in ((Delivery.farmer_id, farmer_id), (Delivery.centre_id, centre_id),
                     (Delivery.crop_id, crop_id), (Delivery.season_id, season_id), (Delivery.status, status)):
        if val:
            stmt = stmt.where(col == val)
    if date_from:
        stmt = stmt.where(Delivery.captured_at >= date_from)
    if date_to:
        stmt = stmt.where(Delivery.captured_at < date_to)
    if mine:
        stmt = stmt.where(Delivery.recorded_by == actor.id)

    agg = db.execute(select(func.count(), func.coalesce(func.sum(Delivery.net_weight), 0))
                     .select_from(stmt.where(Delivery.status == "recorded").subquery())).one()
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.options(*_load_options()).order_by(Delivery.captured_at.desc())
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total, Decimal(agg[1])


def get_delivery(db: Session, actor: User, delivery_id: uuid.UUID) -> Delivery:
    d = db.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.organization_id == org_id(actor))
                  .options(*_load_options(),
                           selectinload(Delivery.amendments).selectinload(DeliveryAmendment.requester)))
    allowed = restricted_centre_ids(actor)
    if d is None or (allowed is not None and d.centre_id not in allowed):
        raise NotFoundError("Delivery not found")
    return d


def _ensure_not_batched(db: Session, d: Delivery) -> None:
    """Once a delivery is aggregated, changing it would silently break batch, warehouse and
    payout figures. It must first be removed from its (still open) batch."""
    from app.models import AggregationBatch, BatchDelivery
    row = db.execute(select(AggregationBatch.batch_no, AggregationBatch.status)
                     .join(BatchDelivery, BatchDelivery.batch_id == AggregationBatch.id)
                     .where(BatchDelivery.delivery_id == d.id)).first()
    if row:
        hint = "remove it from the batch first" if row.status == "open" else "the batch is already closed"
        raise ConflictError(f"Delivery is part of batch {row.batch_no}; {hint}")


def _values(d: Delivery) -> dict:
    return {"gross_weight": str(d.gross_weight), "tare_weight": str(d.tare_weight),
            "net_weight": str(d.net_weight), "grade_id": str(d.grade_id) if d.grade_id else None, "notes": d.notes}


def request_amendment(db: Session, actor: User, delivery_id: uuid.UUID, data: AmendmentRequest) -> Delivery:
    d = get_delivery(db, actor, delivery_id)
    if d.status == "voided":
        raise ValidationFailedError("A voided delivery cannot be amended")
    _ensure_not_batched(db, d)
    if any(a.status == "pending" for a in d.amendments):
        raise ConflictError("This delivery already has a pending correction")
    gross = (data.gross_weight if data.gross_weight is not None else d.gross_weight).quantize(Q3)
    tare = (data.tare_weight if data.tare_weight is not None else d.tare_weight).quantize(Q3)
    if gross - tare <= 0:
        raise ValidationFailedError("Corrected net weight must be greater than zero")
    if data.grade_id:
        g = db.get(CropGrade, data.grade_id)
        if g is None or g.crop_id != d.crop_id:
            raise ValidationFailedError("Grade is not valid for this crop")
    new = {"gross_weight": str(gross), "tare_weight": str(tare), "net_weight": str(gross - tare),
           "grade_id": str(data.grade_id) if data.grade_id else (str(d.grade_id) if d.grade_id else None),
           "notes": data.notes if data.notes is not None else d.notes}
    old = _values(d)
    if new == old:
        raise ValidationFailedError("The correction does not change anything")
    a = DeliveryAmendment(delivery_id=d.id, requested_by=actor.id, reason=data.reason, old_values=old, new_values=new)
    db.add(a)
    db.flush()
    audit_service.record(db, action="delivery.amend_request", user_id=actor.id, organization_id=d.organization_id,
                         entity_type="delivery", entity_id=d.id, before=old, after=new, reason=data.reason)
    db.commit()
    db.expire(d, ["amendments"])
    return get_delivery(db, actor, d.id)


def review_amendment(db: Session, actor: User, delivery_id: uuid.UUID, amendment_id: uuid.UUID,
                     approve: bool, note: str | None) -> Delivery:
    d = get_delivery(db, actor, delivery_id)
    a = next((x for x in d.amendments if x.id == amendment_id), None)
    if a is None:
        raise NotFoundError("Correction not found")
    if a.status != "pending":
        raise ConflictError(f"Correction already {a.status}")
    if a.requested_by == actor.id:
        raise PermissionDeniedError("You cannot approve your own correction")  # separation of duties
    if approve:
        _ensure_not_batched(db, d)
    if approve and _values(d) != a.old_values:
        raise ConflictError("The delivery changed after this correction was requested; request it again")
    a.status = "approved" if approve else "rejected"
    a.reviewed_by, a.reviewed_at, a.review_note = actor.id, datetime.now(UTC), note
    if approve:
        nv = a.new_values
        d.gross_weight, d.tare_weight = Decimal(nv["gross_weight"]), Decimal(nv["tare_weight"])
        d.net_weight = d.gross_weight - d.tare_weight
        d.grade_id = uuid.UUID(nv["grade_id"]) if nv["grade_id"] else None
        d.notes = nv["notes"]
    audit_service.record(db, action=f"delivery.amend_{a.status}", user_id=actor.id,
                         organization_id=d.organization_id, entity_type="delivery", entity_id=d.id,
                         before=a.old_values, after=a.new_values if approve else None, reason=note or a.reason)
    db.commit()
    return get_delivery(db, actor, d.id)


def void_delivery(db: Session, actor: User, delivery_id: uuid.UUID, reason: str) -> Delivery:
    d = get_delivery(db, actor, delivery_id)
    if d.status == "voided":
        raise ConflictError("Delivery is already voided")
    _ensure_not_batched(db, d)
    d.status, d.void_reason, d.voided_by, d.voided_at = "voided", reason, actor.id, datetime.now(UTC)
    for a in d.amendments:
        if a.status == "pending":
            a.status, a.reviewed_by, a.reviewed_at, a.review_note = "rejected", actor.id, d.voided_at, "Delivery voided"
    audit_service.record(db, action="delivery.void", user_id=actor.id, organization_id=d.organization_id,
                         entity_type="delivery", entity_id=d.id, before={"status": "recorded"},
                         after={"status": "voided"}, reason=reason)
    db.commit()
    return get_delivery(db, actor, d.id)


def pending_amendments(db: Session, actor: User) -> list[DeliveryAmendment]:
    stmt = (select(DeliveryAmendment).join(Delivery).where(Delivery.organization_id == org_id(actor),
                                                           DeliveryAmendment.status == "pending")
            .options(selectinload(DeliveryAmendment.delivery).options(*_load_options()),
                     selectinload(DeliveryAmendment.requester))
            .order_by(DeliveryAmendment.created_at))
    return list(db.scalars(stmt))


def sync_farmers(db: Session, actor: User, since: datetime | None) -> list[Farmer]:
    """Farmers to cache offline. Clerks get farmers of their centres plus unassigned ones."""
    stmt = select(Farmer).where(Farmer.organization_id == org_id(actor))
    allowed = restricted_centre_ids(actor)
    if allowed is not None:
        stmt = stmt.where(or_(Farmer.home_centre_id.in_(allowed), Farmer.home_centre_id.is_(None)))
    if since:
        stmt = stmt.where(Farmer.updated_at > since)
    return list(db.scalars(stmt.order_by(Farmer.full_name)))
