"""Organization profile, collection centres, crops/grades and seasons."""
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models import CollectionCentre, Crop, CropGrade, Organization, Season, User
from app.schemas.reference import (
    CentreCreate, CentreUpdate, CropCreate, CropUpdate, GradeCreate, OrganizationUpdate, SeasonCreate, SeasonUpdate,
)
from app.services import audit_service
from app.services.scope import org_id, restricted_centre_ids


def _commit_unique(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(message) from exc


def _changes(obj, data) -> tuple[dict, dict]:
    """Apply only the fields the client sent; return (before, after) for the audit log."""
    before, after = {}, {}
    for field, value in data.model_dump(exclude_unset=True).items():
        old = getattr(obj, field)
        if old != value:
            before[field], after[field] = str(old) if old is not None else None, str(value) if value is not None else None
            setattr(obj, field, value)
    return before, after


# ---------------- Organization ----------------
def get_organization(db: Session, actor: User) -> Organization:
    return db.get(Organization, org_id(actor))


def update_organization(db: Session, actor: User, data: OrganizationUpdate) -> Organization:
    org = get_organization(db, actor)
    before, after = _changes(org, data)
    if after:
        audit_service.record(db, action="organization.update", user_id=actor.id, organization_id=org.id,
                             entity_type="organization", entity_id=org.id, before=before, after=after)
    _commit_unique(db, "Registration number already used")
    return org


# ---------------- Centres ----------------
def list_centres(db: Session, actor: User, q: str | None = None, status: str | None = None) -> list[CollectionCentre]:
    stmt = (select(CollectionCentre).where(CollectionCentre.organization_id == org_id(actor))
            .options(selectinload(CollectionCentre.users)).order_by(CollectionCentre.code))
    allowed = restricted_centre_ids(actor)
    if allowed is not None:
        stmt = stmt.where(CollectionCentre.id.in_(allowed))
    if q:
        stmt = stmt.where(or_(CollectionCentre.name.ilike(f"%{q}%"), CollectionCentre.code.ilike(f"%{q}%"),
                              CollectionCentre.village.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(CollectionCentre.status == status)
    return list(db.scalars(stmt))


def get_centre(db: Session, actor: User, centre_id: uuid.UUID) -> CollectionCentre:
    c = db.scalar(select(CollectionCentre).where(CollectionCentre.id == centre_id,
                                                 CollectionCentre.organization_id == org_id(actor))
                  .options(selectinload(CollectionCentre.users)))
    allowed = restricted_centre_ids(actor)
    if c is None or (allowed is not None and c.id not in allowed):
        raise NotFoundError("Collection centre not found")
    return c


def create_centre(db: Session, actor: User, data: CentreCreate) -> CollectionCentre:
    c = CollectionCentre(organization_id=org_id(actor), **data.model_dump() | {"code": data.code.upper()})
    db.add(c)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Centre code {data.code.upper()} already exists") from exc
    audit_service.record(db, action="centre.create", user_id=actor.id, organization_id=c.organization_id,
                         entity_type="centre", entity_id=c.id, after={"code": c.code, "name": c.name})
    db.commit()
    return c


def update_centre(db: Session, actor: User, centre_id: uuid.UUID, data: CentreUpdate) -> CollectionCentre:
    c = get_centre(db, actor, centre_id)
    before, after = _changes(c, data)
    if after:
        audit_service.record(db, action="centre.update", user_id=actor.id, organization_id=c.organization_id,
                             entity_type="centre", entity_id=c.id, before=before, after=after)
    db.commit()
    return c


def set_centre_staff(db: Session, actor: User, centre_id: uuid.UUID, user_ids: list[uuid.UUID]) -> CollectionCentre:
    c = get_centre(db, actor, centre_id)
    users = list(db.scalars(select(User).where(User.id.in_(user_ids), User.organization_id == c.organization_id)))
    if len(users) != len(set(user_ids)):
        raise ValidationFailedError("User not found in this AMCOS")
    before = sorted(u.email for u in c.users)
    c.users = users
    audit_service.record(db, action="centre.staff_update", user_id=actor.id, organization_id=c.organization_id,
                         entity_type="centre", entity_id=c.id, before={"staff": before},
                         after={"staff": sorted(u.email for u in users)})
    db.commit()
    return c


# ---------------- Crops ----------------
def list_crops(db: Session, actor: User, active_only: bool = False) -> list[Crop]:
    stmt = (select(Crop).where(Crop.organization_id == org_id(actor))
            .options(selectinload(Crop.grades)).order_by(Crop.name))
    if active_only:
        stmt = stmt.where(Crop.is_active.is_(True))
    return list(db.scalars(stmt))


def get_crop(db: Session, actor: User, crop_id: uuid.UUID) -> Crop:
    crop = db.scalar(select(Crop).where(Crop.id == crop_id, Crop.organization_id == org_id(actor))
                     .options(selectinload(Crop.grades)))
    if crop is None:
        raise NotFoundError("Crop not found")
    return crop


def create_crop(db: Session, actor: User, data: CropCreate) -> Crop:
    crop = Crop(organization_id=org_id(actor), code=data.code.upper(), name=data.name, unit=data.unit,
                rules=data.rules.model_dump(mode="json", exclude_none=True),
                grades=[CropGrade(code=g.code.upper(), name=g.name) for g in data.grades])
    db.add(crop)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Crop code (or a grade code) already exists") from exc
    audit_service.record(db, action="crop.create", user_id=actor.id, organization_id=crop.organization_id,
                         entity_type="crop", entity_id=crop.id, after={"code": crop.code, "rules": crop.rules})
    db.commit()
    return crop


def update_crop(db: Session, actor: User, crop_id: uuid.UUID, data: CropUpdate) -> Crop:
    crop = get_crop(db, actor, crop_id)
    before = {"name": crop.name, "is_active": crop.is_active, "rules": crop.rules}
    if data.name is not None:
        crop.name = data.name
    if data.is_active is not None:
        crop.is_active = data.is_active
    if data.rules is not None:
        crop.rules = data.rules.model_dump(mode="json", exclude_none=True)
    audit_service.record(db, action="crop.update", user_id=actor.id, organization_id=crop.organization_id,
                         entity_type="crop", entity_id=crop.id, before=before,
                         after={"name": crop.name, "is_active": crop.is_active, "rules": crop.rules})
    db.commit()
    return crop


def add_grade(db: Session, actor: User, crop_id: uuid.UUID, data: GradeCreate) -> Crop:
    crop = get_crop(db, actor, crop_id)
    crop.grades.append(CropGrade(code=data.code.upper(), name=data.name))
    audit_service.record(db, action="crop.grade_add", user_id=actor.id, organization_id=crop.organization_id,
                         entity_type="crop", entity_id=crop.id, after={"grade": data.code.upper()})
    _commit_unique(db, f"Grade {data.code.upper()} already exists for this crop")
    return crop


def set_grade_active(db: Session, actor: User, crop_id: uuid.UUID, grade_id: uuid.UUID, is_active: bool) -> Crop:
    crop = get_crop(db, actor, crop_id)
    grade = next((g for g in crop.grades if g.id == grade_id), None)
    if grade is None:
        raise NotFoundError("Grade not found")
    grade.is_active = is_active
    audit_service.record(db, action="crop.grade_update", user_id=actor.id, organization_id=crop.organization_id,
                         entity_type="crop", entity_id=crop.id, after={"grade": grade.code, "is_active": is_active})
    db.commit()
    return crop


# ---------------- Seasons ----------------
def list_seasons(db: Session, actor: User) -> list[Season]:
    return list(db.scalars(select(Season).where(Season.organization_id == org_id(actor))
                           .order_by(Season.start_date.desc())))


def _check_overlap(db: Session, org: uuid.UUID, start, end, exclude: uuid.UUID | None = None) -> None:
    stmt = select(func.count()).select_from(Season).where(
        Season.organization_id == org, Season.start_date <= end, Season.end_date >= start)
    if exclude:
        stmt = stmt.where(Season.id != exclude)
    if db.scalar(stmt):
        raise ValidationFailedError("Season dates overlap an existing season")


def create_season(db: Session, actor: User, data: SeasonCreate) -> Season:
    org = org_id(actor)
    _check_overlap(db, org, data.start_date, data.end_date)
    s = Season(organization_id=org, **data.model_dump())
    db.add(s)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A season with this name already exists") from exc
    audit_service.record(db, action="season.create", user_id=actor.id, organization_id=org,
                         entity_type="season", entity_id=s.id, after=data.model_dump(mode="json"))
    db.commit()
    return s


def update_season(db: Session, actor: User, season_id: uuid.UUID, data: SeasonUpdate) -> Season:
    s = db.scalar(select(Season).where(Season.id == season_id, Season.organization_id == org_id(actor)))
    if s is None:
        raise NotFoundError("Season not found")
    start, end = data.start_date or s.start_date, data.end_date or s.end_date
    if end < start:
        raise ValidationFailedError("end_date must be on or after start_date")
    _check_overlap(db, s.organization_id, start, end, exclude=s.id)
    before, after = _changes(s, data)
    if after:
        audit_service.record(db, action="season.update", user_id=actor.id, organization_id=s.organization_id,
                             entity_type="season", entity_id=s.id, before=before, after=after)
    _commit_unique(db, "A season with this name already exists")
    return s
