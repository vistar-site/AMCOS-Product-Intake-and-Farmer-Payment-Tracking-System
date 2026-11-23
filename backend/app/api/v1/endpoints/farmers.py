import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import Farmer, User
from app.schemas.common import Page
from app.schemas.farmer import (
    FarmerCreate, FarmerFinancialRead, FarmerRead, FarmerStatusUpdate, FarmerSummary, FarmerUpdate,
)
from app.services import farmer_service as svc

router = APIRouter(prefix="/farmers", tags=["farmers"])


def _shape(user: User, farmer: Farmer) -> FarmerRead:
    """Payment details are only serialized for users allowed to see them."""
    schema = FarmerFinancialRead if "farmer.view_financial" in user.permission_codes else FarmerRead
    return schema.model_validate(farmer)


@router.get("", response_model=Page[FarmerFinancialRead | FarmerRead])
def search(q: str | None = Query(None, max_length=100, description="Name, membership number or phone"),
           village: str | None = Query(None, max_length=100), centre_id: uuid.UUID | None = None,
           status: str | None = Query(None, pattern="^(active|inactive|suspended)$"),
           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           user: User = Depends(require_permission("farmer.view")), db: Session = Depends(get_db)):
    items, total = svc.search_farmers(db, user, q=q, village=village, centre_id=centre_id, status=status,
                                      page=page, page_size=page_size)
    return Page(items=[_shape(user, f) for f in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=FarmerFinancialRead | FarmerRead, status_code=status.HTTP_201_CREATED)
def create(body: FarmerCreate, user: User = Depends(require_permission("farmer.create")), db: Session = Depends(get_db)):
    return _shape(user, svc.create_farmer(db, user, body))


@router.get("/{farmer_id}", response_model=FarmerFinancialRead | FarmerRead)
def get(farmer_id: uuid.UUID, user: User = Depends(require_permission("farmer.view")), db: Session = Depends(get_db)):
    return _shape(user, svc.get_farmer(db, user, farmer_id))


@router.patch("/{farmer_id}", response_model=FarmerFinancialRead | FarmerRead)
def update(farmer_id: uuid.UUID, body: FarmerUpdate, user: User = Depends(require_permission("farmer.update")),
           db: Session = Depends(get_db)):
    return _shape(user, svc.update_farmer(db, user, farmer_id, body))


@router.post("/{farmer_id}/status", response_model=FarmerFinancialRead | FarmerRead)
def set_status(farmer_id: uuid.UUID, body: FarmerStatusUpdate, user: User = Depends(require_permission("farmer.update")),
               db: Session = Depends(get_db)):
    return _shape(user, svc.set_status(db, user, farmer_id, body.status, body.reason))


@router.get("/{farmer_id}/summary", response_model=FarmerSummary)
def summary(farmer_id: uuid.UUID, user: User = Depends(require_permission("farmer.view")), db: Session = Depends(get_db)):
    return svc.summary(db, user, farmer_id)
