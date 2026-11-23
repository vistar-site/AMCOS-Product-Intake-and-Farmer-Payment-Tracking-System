import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import User
from app.schemas.warehouse import (
    AllocationRead, AuctionCreate, AuctionRead, BatchAddDeliveries, BatchCreate, BatchRead, DeliveryTrace,
    DiscrepancyRead, DiscrepancyResolve, DispatchCreate, DispatchRead, EligibleDelivery, LotCreate, ReceiptCreate,
    Reconciliation, SellableBatch, WarehouseCreate, WarehouseRead,
)
from app.services import auction_service as auctions
from app.services import warehouse_service as wh

router = APIRouter()
db_dep = Depends(get_db)


# ---- Warehouses registry
@router.get("/warehouses", response_model=list[WarehouseRead], tags=["warehouse"])
def list_warehouses(u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.list_warehouses(db, u)


@router.post("/warehouses", response_model=WarehouseRead, status_code=201, tags=["warehouse"])
def create_warehouse(body: WarehouseCreate, u: User = Depends(require_permission("warehouse.manage")), db: Session = db_dep):
    return wh.create_warehouse(db, u, body.model_dump())


# ---- Batches
@router.get("/batches", response_model=list[BatchRead], tags=["aggregation"])
def list_batches(status: str | None = None, crop_id: uuid.UUID | None = None, centre_id: uuid.UUID | None = None,
                 season_id: uuid.UUID | None = None, u: User = Depends(require_permission("delivery.view")),
                 db: Session = db_dep):
    return wh.list_batches(db, u, status=status, crop_id=crop_id, centre_id=centre_id, season_id=season_id)


@router.post("/batches", response_model=BatchRead, status_code=201, tags=["aggregation"])
def create_batch(body: BatchCreate, u: User = Depends(require_permission("batch.manage")), db: Session = db_dep):
    return wh.create_batch(db, u, body.crop_id, body.season_id, body.centre_id, body.notes)


@router.get("/batches/{batch_id}", response_model=BatchRead, tags=["aggregation"])
def get_batch(batch_id: uuid.UUID, u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.get_batch(db, u, batch_id)


@router.get("/batches/{batch_id}/eligible-deliveries", response_model=list[EligibleDelivery], tags=["aggregation"])
def eligible(batch_id: uuid.UUID, u: User = Depends(require_permission("batch.manage")), db: Session = db_dep):
    return wh.eligible_deliveries(db, u, batch_id)


@router.post("/batches/{batch_id}/deliveries", response_model=BatchRead, tags=["aggregation"])
def add_deliveries(batch_id: uuid.UUID, body: BatchAddDeliveries, u: User = Depends(require_permission("batch.manage")),
                   db: Session = db_dep):
    return wh.add_deliveries(db, u, batch_id, body.delivery_ids)


@router.delete("/batches/{batch_id}/deliveries/{delivery_id}", response_model=BatchRead, tags=["aggregation"])
def remove_delivery(batch_id: uuid.UUID, delivery_id: uuid.UUID, u: User = Depends(require_permission("batch.manage")),
                    db: Session = db_dep):
    return wh.remove_delivery(db, u, batch_id, delivery_id)


@router.post("/batches/{batch_id}/close", response_model=BatchRead, tags=["aggregation"])
def close_batch(batch_id: uuid.UUID, u: User = Depends(require_permission("batch.manage")), db: Session = db_dep):
    return wh.close_batch(db, u, batch_id)


@router.get("/batches/{batch_id}/reconciliation", response_model=Reconciliation, tags=["reconciliation"])
def reconcile(batch_id: uuid.UUID, u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.reconciliation(db, u, batch_id)


@router.get("/deliveries/{delivery_id}/trace", response_model=DeliveryTrace, tags=["reconciliation"])
def trace(delivery_id: uuid.UUID, u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.trace_delivery(db, u, delivery_id)


# ---- Dispatches & receipts
@router.get("/dispatches", response_model=list[DispatchRead], tags=["warehouse"])
def list_dispatches(status: str | None = Query(None, pattern="^(in_transit|received)$"),
                    u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.list_dispatches(db, u, status)


@router.post("/dispatches", response_model=DispatchRead, status_code=201, tags=["warehouse"])
def create_dispatch(body: DispatchCreate, u: User = Depends(require_permission("dispatch.manage")), db: Session = db_dep):
    return wh.create_dispatch(db, u, body.warehouse_id, body.dispatch_date, body.vehicle_reg, body.driver_name,
                              body.notes, [(l.batch_id, l.dispatched_weight) for l in body.lines])


@router.get("/dispatches/{dispatch_id}", response_model=DispatchRead, tags=["warehouse"])
def get_dispatch(dispatch_id: uuid.UUID, u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.get_dispatch(db, u, dispatch_id)


@router.post("/dispatches/{dispatch_id}/receipt", response_model=DispatchRead, status_code=201, tags=["warehouse"])
def record_receipt(dispatch_id: uuid.UUID, body: ReceiptCreate,
                   u: User = Depends(require_permission("warehouse_receipt.manage")), db: Session = db_dep):
    return wh.record_receipt(db, u, dispatch_id, body.receipt_no, body.receipt_date, body.notes,
                             [l.model_dump() for l in body.lines])


# ---- Discrepancies
@router.get("/discrepancies", response_model=list[DiscrepancyRead], tags=["reconciliation"])
def list_discrepancies(status: str | None = Query(None, pattern="^(open|explained|accepted)$"),
                       u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return wh.list_discrepancies(db, u, status)


@router.post("/discrepancies/{discrepancy_id}/resolve", response_model=DiscrepancyRead, tags=["reconciliation"])
def resolve(discrepancy_id: uuid.UUID, body: DiscrepancyResolve,
            u: User = Depends(require_permission("reconciliation.approve")), db: Session = db_dep):
    return wh.resolve_discrepancy(db, u, discrepancy_id, body.explanation)


# ---- Auctions
@router.get("/auctions", response_model=list[AuctionRead], tags=["auctions"])
def list_auctions(status: str | None = Query(None, pattern="^(draft|approved)$"), crop_id: uuid.UUID | None = None,
                  u: User = Depends(require_permission("auction.view")), db: Session = db_dep):
    return auctions.list_auctions(db, u, status, crop_id)


@router.post("/auctions", response_model=AuctionRead, status_code=status.HTTP_201_CREATED, tags=["auctions"])
def create_auction(body: AuctionCreate, u: User = Depends(require_permission("auction.manage")), db: Session = db_dep):
    return auctions.create_auction(db, u, body.model_dump())


@router.get("/auctions/sellable-batches", response_model=list[SellableBatch], tags=["auctions"])
def sellable(crop_id: uuid.UUID, u: User = Depends(require_permission("auction.manage")), db: Session = db_dep):
    return [SellableBatch(id=b.id, batch_no=b.batch_no, centre_name=b.centre.name, available_weight=w)
            for b, w in auctions.sellable_batches(db, u, crop_id)]


@router.get("/auctions/{auction_id}", response_model=AuctionRead, tags=["auctions"])
def get_auction(auction_id: uuid.UUID, u: User = Depends(require_permission("auction.view")), db: Session = db_dep):
    return auctions.get_auction(db, u, auction_id)


@router.post("/auctions/{auction_id}/lots", response_model=AuctionRead, status_code=201, tags=["auctions"])
def add_lot(auction_id: uuid.UUID, body: LotCreate, u: User = Depends(require_permission("auction.manage")),
            db: Session = db_dep):
    return auctions.add_lot(db, u, auction_id, body.model_dump())


@router.delete("/auctions/{auction_id}/lots/{lot_id}", response_model=AuctionRead, tags=["auctions"])
def remove_lot(auction_id: uuid.UUID, lot_id: uuid.UUID, u: User = Depends(require_permission("auction.manage")),
               db: Session = db_dep):
    return auctions.remove_lot(db, u, auction_id, lot_id)


@router.post("/auctions/{auction_id}/approve", response_model=AuctionRead, tags=["auctions"])
def approve(auction_id: uuid.UUID, u: User = Depends(require_permission("auction.approve")), db: Session = db_dep):
    return auctions.approve_auction(db, u, auction_id)


@router.get("/auctions/{auction_id}/lots/{lot_id}/allocations", response_model=list[AllocationRead], tags=["auctions"])
def allocations(auction_id: uuid.UUID, lot_id: uuid.UUID, u: User = Depends(require_permission("auction.view")),
                db: Session = db_dep):
    return auctions.lot_allocations(db, u, auction_id, lot_id)
