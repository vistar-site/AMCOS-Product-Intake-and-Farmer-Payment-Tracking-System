import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import Organization, User
from app.schemas.common import Page
from app.schemas.delivery import (
    AmendmentRead, AmendmentRequest, AmendmentReview, DeliveryCreate, DeliveryCreateResult, DeliveryDetail,
    DeliveryRead, SyncFarmer, SyncRequest, SyncResponse, VoidRequest,
)
from app.services import delivery_service as svc
from app.services.notification_service import process_queue_background
from app.services.receipt_pdf import render_receipt

router = APIRouter(tags=["deliveries"])


class DeliveryPage(Page[DeliveryRead]):
    total_net_weight: Decimal  # sum over ALL filtered (non-voided) rows, not just this page


@router.post("/deliveries", response_model=DeliveryCreateResult)
def create(body: DeliveryCreate, response: Response, background: BackgroundTasks,
           user: User = Depends(require_permission("delivery.create")), db: Session = Depends(get_db)):
    delivery, created, warnings = svc.create_online(db, user, body)
    if created:
        background.add_task(process_queue_background, user.organization_id)  # SMS after the response
    response.status_code = 201 if created else 200
    return DeliveryCreateResult(delivery=delivery, created=created, warnings=warnings)


@router.get("/deliveries", response_model=DeliveryPage)
def list_deliveries(
    q: str | None = Query(None, max_length=100, description="Receipt no., farmer name or membership no."),
    farmer_id: uuid.UUID | None = None, centre_id: uuid.UUID | None = None, crop_id: uuid.UUID | None = None,
    season_id: uuid.UUID | None = None, status: str | None = Query(None, pattern="^(recorded|voided)$"),
    date_from: datetime | None = None, date_to: datetime | None = None, mine: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(require_permission("delivery.view")), db: Session = Depends(get_db),
):
    items, total, kg = svc.list_deliveries(db, user, q=q, farmer_id=farmer_id, centre_id=centre_id, crop_id=crop_id,
                                           season_id=season_id, status=status, date_from=date_from, date_to=date_to,
                                           mine=mine, page=page, page_size=page_size)
    return DeliveryPage(items=items, total=total, page=page, page_size=page_size, total_net_weight=kg)


@router.get("/deliveries/amendments/pending", response_model=list[AmendmentRead])
def pending(user: User = Depends(require_permission("delivery.amend_approve")), db: Session = Depends(get_db)):
    return svc.pending_amendments(db, user)


@router.get("/deliveries/{delivery_id}", response_model=DeliveryDetail)
def get(delivery_id: uuid.UUID, user: User = Depends(require_permission("delivery.view")), db: Session = Depends(get_db)):
    return svc.get_delivery(db, user, delivery_id)


@router.get("/deliveries/{delivery_id}/receipt.pdf", response_class=Response)
def receipt_pdf(delivery_id: uuid.UUID, user: User = Depends(require_permission("delivery.view")),
                db: Session = Depends(get_db)):
    d = svc.get_delivery(db, user, delivery_id)
    pdf = render_receipt(d, db.get(Organization, d.organization_id))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="receipt-{d.receipt_no}.pdf"'})


@router.post("/deliveries/{delivery_id}/amendments", response_model=DeliveryDetail, status_code=201)
def request_amendment(delivery_id: uuid.UUID, body: AmendmentRequest,
                      user: User = Depends(require_permission("delivery.amend_request")), db: Session = Depends(get_db)):
    return svc.request_amendment(db, user, delivery_id, body)


@router.post("/deliveries/{delivery_id}/amendments/{amendment_id}/review", response_model=DeliveryDetail)
def review_amendment(delivery_id: uuid.UUID, amendment_id: uuid.UUID, body: AmendmentReview,
                     user: User = Depends(require_permission("delivery.amend_approve")), db: Session = Depends(get_db)):
    return svc.review_amendment(db, user, delivery_id, amendment_id, body.decision == "approve", body.note)


@router.post("/deliveries/{delivery_id}/void", response_model=DeliveryDetail)
def void(delivery_id: uuid.UUID, body: VoidRequest, user: User = Depends(require_permission("delivery.amend_approve")),
         db: Session = Depends(get_db)):
    return svc.void_delivery(db, user, delivery_id, body.reason)


# --- Offline sync ---
@router.post("/sync/deliveries", response_model=SyncResponse, tags=["sync"])
def sync_deliveries(body: SyncRequest, background: BackgroundTasks,
                    user: User = Depends(require_permission("delivery.create")), db: Session = Depends(get_db)):
    results = svc.sync(db, user, body.device_id, body.deliveries)
    background.add_task(process_queue_background, user.organization_id)
    return SyncResponse(results=results, server_time=datetime.now(UTC))


@router.get("/sync/farmers", response_model=list[SyncFarmer], tags=["sync"])
def sync_farmers(since: datetime | None = None, user: User = Depends(require_permission("farmer.view")),
                 db: Session = Depends(get_db)):
    return svc.sync_farmers(db, user, since)
