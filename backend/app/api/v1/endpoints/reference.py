"""Organization, collection centres, crops/grades and seasons."""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import User
from app.schemas.reference import (
    CentreCreate, CentreRead, CentreStaffUpdate, CentreUpdate, CropCreate, CropRead, CropUpdate, GradeCreate,
    OrganizationRead, OrganizationUpdate, SeasonCreate, SeasonRead, SeasonUpdate,
)
from app.services import reference_service as svc

router = APIRouter()


# --- Organization (the current user's AMCOS) ---
@router.get("/organization", response_model=OrganizationRead, tags=["organization"])
def get_org(user: User = Depends(require_permission("centre.view")), db: Session = Depends(get_db)):
    return svc.get_organization(db, user)


@router.patch("/organization", response_model=OrganizationRead, tags=["organization"])
def update_org(body: OrganizationUpdate, user: User = Depends(require_permission("settings.manage")),
               db: Session = Depends(get_db)):
    return svc.update_organization(db, user, body)


# --- Centres ---
@router.get("/centres", response_model=list[CentreRead], tags=["centres"])
def list_centres(q: str | None = Query(None, max_length=100), status: str | None = Query(None, pattern="^(active|inactive)$"),
                 user: User = Depends(require_permission("centre.view")), db: Session = Depends(get_db)):
    return svc.list_centres(db, user, q, status)


@router.post("/centres", response_model=CentreRead, status_code=status.HTTP_201_CREATED, tags=["centres"])
def create_centre(body: CentreCreate, user: User = Depends(require_permission("centre.manage")),
                  db: Session = Depends(get_db)):
    return svc.create_centre(db, user, body)


@router.get("/centres/{centre_id}", response_model=CentreRead, tags=["centres"])
def get_centre(centre_id: uuid.UUID, user: User = Depends(require_permission("centre.view")),
               db: Session = Depends(get_db)):
    return svc.get_centre(db, user, centre_id)


@router.patch("/centres/{centre_id}", response_model=CentreRead, tags=["centres"])
def update_centre(centre_id: uuid.UUID, body: CentreUpdate, user: User = Depends(require_permission("centre.manage")),
                  db: Session = Depends(get_db)):
    return svc.update_centre(db, user, centre_id, body)


@router.put("/centres/{centre_id}/staff", response_model=CentreRead, tags=["centres"])
def set_staff(centre_id: uuid.UUID, body: CentreStaffUpdate, user: User = Depends(require_permission("centre.manage")),
              db: Session = Depends(get_db)):
    return svc.set_centre_staff(db, user, centre_id, body.user_ids)


# --- Crops ---
@router.get("/crops", response_model=list[CropRead], tags=["crops"])
def list_crops(active_only: bool = False, user: User = Depends(require_permission("crop.view")),
               db: Session = Depends(get_db)):
    return svc.list_crops(db, user, active_only)


@router.post("/crops", response_model=CropRead, status_code=status.HTTP_201_CREATED, tags=["crops"])
def create_crop(body: CropCreate, user: User = Depends(require_permission("crop.manage")), db: Session = Depends(get_db)):
    return svc.create_crop(db, user, body)


@router.patch("/crops/{crop_id}", response_model=CropRead, tags=["crops"])
def update_crop(crop_id: uuid.UUID, body: CropUpdate, user: User = Depends(require_permission("crop.manage")),
                db: Session = Depends(get_db)):
    return svc.update_crop(db, user, crop_id, body)


@router.post("/crops/{crop_id}/grades", response_model=CropRead, status_code=status.HTTP_201_CREATED, tags=["crops"])
def add_grade(crop_id: uuid.UUID, body: GradeCreate, user: User = Depends(require_permission("crop.manage")),
              db: Session = Depends(get_db)):
    return svc.add_grade(db, user, crop_id, body)


@router.patch("/crops/{crop_id}/grades/{grade_id}", response_model=CropRead, tags=["crops"])
def set_grade(crop_id: uuid.UUID, grade_id: uuid.UUID, is_active: bool,
              user: User = Depends(require_permission("crop.manage")), db: Session = Depends(get_db)):
    return svc.set_grade_active(db, user, crop_id, grade_id, is_active)


# --- Seasons ---
@router.get("/seasons", response_model=list[SeasonRead], tags=["seasons"])
def list_seasons(user: User = Depends(require_permission("crop.view")), db: Session = Depends(get_db)):
    return svc.list_seasons(db, user)


@router.post("/seasons", response_model=SeasonRead, status_code=status.HTTP_201_CREATED, tags=["seasons"])
def create_season(body: SeasonCreate, user: User = Depends(require_permission("crop.manage")),
                  db: Session = Depends(get_db)):
    return svc.create_season(db, user, body)


@router.patch("/seasons/{season_id}", response_model=SeasonRead, tags=["seasons"])
def update_season(season_id: uuid.UUID, body: SeasonUpdate, user: User = Depends(require_permission("crop.manage")),
                  db: Session = Depends(get_db)):
    return svc.update_season(db, user, season_id, body)
