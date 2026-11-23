import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

KG = dict(max_digits=12, decimal_places=3)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Ref(ORM):
    id: uuid.UUID
    code: str
    name: str


class NameRef(ORM):
    id: uuid.UUID
    name: str


# ---------------- Batches
class BatchCreate(BaseModel):
    crop_id: uuid.UUID
    season_id: uuid.UUID
    centre_id: uuid.UUID
    notes: str | None = Field(None, max_length=1000)


class BatchAddDeliveries(BaseModel):
    delivery_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)


class FarmerMini(ORM):
    id: uuid.UUID
    full_name: str
    membership_no: str


class MemberDelivery(ORM):
    id: uuid.UUID
    receipt_no: str
    captured_at: datetime
    farmer: FarmerMini


class BatchMember(ORM):
    delivery_id: uuid.UUID
    net_weight: Decimal
    delivery: MemberDelivery


class BatchRead(ORM):
    id: uuid.UUID
    batch_no: str
    status: str
    crop: Ref
    season: NameRef
    centre: Ref
    total_net_weight: Decimal | None
    created_at: datetime
    closed_at: datetime | None
    notes: str | None
    members: list[BatchMember]


class EligibleDelivery(ORM):
    id: uuid.UUID
    receipt_no: str
    captured_at: datetime
    net_weight: Decimal
    farmer: FarmerMini


# ---------------- Dispatch & receipt
class DispatchLineIn(BaseModel):
    batch_id: uuid.UUID
    dispatched_weight: Decimal = Field(gt=0, **KG)


class DispatchCreate(BaseModel):
    warehouse_id: uuid.UUID
    dispatch_date: date
    vehicle_reg: str | None = Field(None, max_length=30)
    driver_name: str | None = Field(None, max_length=150)
    notes: str | None = Field(None, max_length=1000)
    lines: list[DispatchLineIn] = Field(min_length=1)


class BatchMini(ORM):
    id: uuid.UUID
    batch_no: str
    status: str
    total_net_weight: Decimal | None


class DispatchLineRead(ORM):
    batch_id: uuid.UUID
    dispatched_weight: Decimal
    batch: BatchMini


class ReceiptLineIn(BaseModel):
    batch_id: uuid.UUID
    received_weight: Decimal = Field(ge=0, **KG)
    rejected_weight: Decimal = Field(Decimal("0"), ge=0, **KG)
    damaged_weight: Decimal = Field(Decimal("0"), ge=0, **KG)


class ReceiptCreate(BaseModel):
    receipt_no: str = Field(min_length=1, max_length=60)
    receipt_date: date
    notes: str | None = Field(None, max_length=1000)
    lines: list[ReceiptLineIn] = Field(min_length=1)


class ReceiptLineRead(ORM):
    batch_id: uuid.UUID
    received_weight: Decimal
    rejected_weight: Decimal
    damaged_weight: Decimal
    accepted_weight: Decimal


class ReceiptRead(ORM):
    id: uuid.UUID
    receipt_no: str
    receipt_date: date
    notes: str | None
    lines: list[ReceiptLineRead]


class WarehouseRef(ORM):
    id: uuid.UUID
    code: str
    name: str


class DispatchRead(ORM):
    id: uuid.UUID
    dispatch_no: str
    warehouse: WarehouseRef
    dispatch_date: date
    vehicle_reg: str | None
    driver_name: str | None
    status: str
    notes: str | None
    lines: list[DispatchLineRead]
    receipt: ReceiptRead | None


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)
    operator_name: str | None = Field(None, max_length=150)
    licence_no: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=200)


class WarehouseRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    operator_name: str | None
    licence_no: str | None
    location: str | None
    is_active: bool


# ---------------- Discrepancies & reconciliation
class DiscrepancyRead(ORM):
    id: uuid.UUID
    batch: BatchMini
    stage: str
    expected_weight: Decimal
    actual_weight: Decimal
    difference: Decimal
    status: str
    explanation: str | None
    resolved_at: datetime | None
    created_at: datetime


class DiscrepancyResolve(BaseModel):
    explanation: str = Field(min_length=10, max_length=2000)


class Reconciliation(BaseModel):
    batch: BatchMini
    farmer_deliveries: int
    delivered_weight: Decimal
    batch_weight: Decimal | None
    dispatched_weight: Decimal | None
    received_weight: Decimal | None
    rejected_weight: Decimal | None
    damaged_weight: Decimal | None
    accepted_weight: Decimal | None
    warehouse_receipt_no: str | None
    sold_weight: Decimal
    sold_value: Decimal
    unsold_weight: Decimal | None
    discrepancies: list[DiscrepancyRead]


class TraceAllocation(BaseModel):
    auction_ref: str
    auction_date: date
    lot_no: str
    price_per_kg: Decimal
    weight_shared: Decimal
    weight_absorbed: Decimal


class DeliveryTrace(BaseModel):
    delivery_id: uuid.UUID
    receipt_no: str
    net_weight: Decimal
    batch: dict | None
    dispatch: dict | None
    warehouse_receipt: dict | None
    allocations: list[TraceAllocation]


# ---------------- Auctions
class AuctionCreate(BaseModel):
    auction_ref: str = Field(min_length=1, max_length=60)
    auction_date: date
    venue: str | None = Field(None, max_length=150)
    crop_id: uuid.UUID
    season_id: uuid.UUID
    notes: str | None = Field(None, max_length=1000)


class LotCreate(BaseModel):
    batch_id: uuid.UUID
    lot_no: str = Field(min_length=1, max_length=40)
    grade_id: uuid.UUID | None = None
    quantity_sold: Decimal = Field(gt=0, **KG)
    price_per_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    buyer: str | None = Field(None, max_length=150)


class GradeMini(ORM):
    id: uuid.UUID
    code: str
    name: str


class LotRead(ORM):
    id: uuid.UUID
    lot_no: str
    batch: BatchMini
    grade: GradeMini | None
    quantity_sold: Decimal
    price_per_kg: Decimal
    total_value: Decimal
    buyer: str | None


class AuctionRead(ORM):
    id: uuid.UUID
    auction_ref: str
    auction_date: date
    venue: str | None
    crop: Ref
    season: NameRef
    status: str
    created_by: uuid.UUID
    approved_at: datetime | None
    notes: str | None
    lots: list[LotRead]


class SellableBatch(BaseModel):
    id: uuid.UUID
    batch_no: str
    centre_name: str
    available_weight: Decimal


class AllocationRead(ORM):
    delivery_id: uuid.UUID
    farmer_id: uuid.UUID
    weight_shared: Decimal
    weight_absorbed: Decimal
    price_per_kg: Decimal
    delivery: MemberDelivery
