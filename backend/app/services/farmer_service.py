"""Farmer registration, search and profile summary."""
import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.database.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models import CollectionCentre, Crop, Delivery, Farmer, Organization, User
from app.schemas.farmer import FarmerCreate, FarmerCropSummary, FarmerSummary, FarmerUpdate
from app.services import audit_service
from app.services.numbering import next_number
from app.services.scope import org_id

FINANCIAL_FIELDS = {"payment_method", "mobile_money_number", "bank_name", "bank_account_no"}


def _normalize_phone(phone: str | None) -> str | None:
    """Store Tanzanian numbers in E.164 (+255...). 0712345678 -> +255712345678."""
    if not phone:
        return None
    p = phone.strip().replace(" ", "")
    if p.startswith("0") and len(p) == 10:
        return "+255" + p[1:]
    if p.startswith("255"):
        return "+" + p
    return p


def _check_centre(db: Session, org: uuid.UUID, centre_id: uuid.UUID | None) -> None:
    if centre_id and not db.scalar(select(CollectionCentre.id).where(
            CollectionCentre.id == centre_id, CollectionCentre.organization_id == org)):
        raise ValidationFailedError("Collection centre not found in this AMCOS")


def search_farmers(db: Session, actor: User, *, q: str | None, village: str | None, centre_id: uuid.UUID | None,
                   status: str | None, page: int, page_size: int) -> tuple[list[Farmer], int]:
    stmt = select(Farmer).where(Farmer.organization_id == org_id(actor))
    if q:
        term = q.strip()
        phone = _normalize_phone(term) if term.replace("+", "").isdigit() else None
        conditions = [func.lower(Farmer.full_name).contains(term.lower()),
                      Farmer.membership_no.ilike(f"{term}%")]
        if phone:
            conditions.append(Farmer.phone == phone)
        stmt = stmt.where(or_(*conditions))
    if village:
        stmt = stmt.where(Farmer.village.ilike(village))
    if centre_id:
        stmt = stmt.where(Farmer.home_centre_id == centre_id)
    if status:
        stmt = stmt.where(Farmer.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.options(selectinload(Farmer.home_centre)).order_by(Farmer.full_name)
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def get_farmer(db: Session, actor: User, farmer_id: uuid.UUID) -> Farmer:
    f = db.scalar(select(Farmer).where(Farmer.id == farmer_id, Farmer.organization_id == org_id(actor))
                  .options(selectinload(Farmer.home_centre)))
    if f is None:
        raise NotFoundError("Farmer not found")
    return f


def create_farmer(db: Session, actor: User, data: FarmerCreate) -> Farmer:
    org = org_id(actor)
    _check_centre(db, org, data.home_centre_id)
    values = data.model_dump(exclude_none=True)
    can_set_financial = "farmer.view_financial" in actor.permission_codes or "farmer.update" in actor.permission_codes
    if not can_set_financial:
        # A clerk may record a mobile money number at registration (it's usually the phone),
        # but not bank details.
        values.pop("bank_name", None)
        values.pop("bank_account_no", None)
    values["phone"] = _normalize_phone(data.phone)
    values["mobile_money_number"] = _normalize_phone(data.mobile_money_number or data.phone)

    if not data.membership_no:
        code = db.get(Organization, org).code
        values["membership_no"] = f"{code}-{next_number(db, org, 'farmer'):04d}"
        # Skip numbers already used by manually entered membership numbers
        while db.scalar(select(Farmer.id).where(Farmer.organization_id == org,
                                                Farmer.membership_no == values["membership_no"])):
            values["membership_no"] = f"{code}-{next_number(db, org, 'farmer'):04d}"
    else:
        values["membership_no"] = data.membership_no.upper()

    farmer = Farmer(organization_id=org, **values)
    db.add(farmer)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Membership number {values['membership_no']} already exists") from exc
    audit_service.record(db, action="farmer.create", user_id=actor.id, organization_id=org, entity_type="farmer",
                         entity_id=farmer.id,
                         after={k: str(v) for k, v in values.items() if k not in FINANCIAL_FIELDS})
    db.commit()
    return get_farmer(db, actor, farmer.id)


def update_farmer(db: Session, actor: User, farmer_id: uuid.UUID, data: FarmerUpdate) -> Farmer:
    farmer = get_farmer(db, actor, farmer_id)
    changes = data.model_dump(exclude_unset=True)
    if "home_centre_id" in changes:
        _check_centre(db, farmer.organization_id, changes["home_centre_id"])
    for key in ("phone", "mobile_money_number"):
        if key in changes:
            changes[key] = _normalize_phone(changes[key])
    before, after = {}, {}
    for key, value in changes.items():
        old = getattr(farmer, key)
        if old != value:
            # Financial values are logged as "changed" without exposing the numbers in the audit log
            masked = key in FINANCIAL_FIELDS - {"payment_method"}
            before[key] = "***" if masked else (str(old) if old is not None else None)
            after[key] = "*** (changed)" if masked else (str(value) if value is not None else None)
            setattr(farmer, key, value)
    if farmer.payment_method == "bank" and not (farmer.bank_name and farmer.bank_account_no):
        raise ValidationFailedError("Bank name and account number are required for bank payments")
    if after:
        audit_service.record(db, action="farmer.update", user_id=actor.id, organization_id=farmer.organization_id,
                             entity_type="farmer", entity_id=farmer.id, before=before, after=after)
    db.commit()
    return farmer


def set_status(db: Session, actor: User, farmer_id: uuid.UUID, status: str, reason: str) -> Farmer:
    farmer = get_farmer(db, actor, farmer_id)
    old = farmer.status
    farmer.status = status
    audit_service.record(db, action="farmer.status_change", user_id=actor.id, organization_id=farmer.organization_id,
                         entity_type="farmer", entity_id=farmer.id, before={"status": old},
                         after={"status": status}, reason=reason)
    db.commit()
    return farmer


def summary(db: Session, actor: User, farmer_id: uuid.UUID) -> FarmerSummary:
    farmer = get_farmer(db, actor, farmer_id)
    rows = db.execute(
        select(Crop.code, Crop.name, func.count(Delivery.id), func.coalesce(func.sum(Delivery.net_weight), 0))
        .join(Crop, Crop.id == Delivery.crop_id)
        .where(Delivery.farmer_id == farmer.id, Delivery.status == "recorded")
        .group_by(Crop.code, Crop.name).order_by(Crop.name)
    ).all()
    last = db.scalar(select(func.max(Delivery.captured_at)).where(
        Delivery.farmer_id == farmer.id, Delivery.status == "recorded"))
    by_crop = [FarmerCropSummary(crop_code=c, crop_name=n, deliveries=k, net_weight=Decimal(w)) for c, n, k, w in rows]
    return FarmerSummary(total_deliveries=sum(r.deliveries for r in by_crop),
                         total_net_weight=sum((r.net_weight for r in by_crop), Decimal("0")),
                         last_delivery_at=last, by_crop=by_crop)
