"""Aggregation, dispatch, warehouse receipts, discrepancies, auctions and allocations.

The traceability chain:

  delivery --(batch_deliveries)--> aggregation_batch --(dispatch_batches)--> warehouse_dispatch
      |                                    |
      |                         warehouse_receipt_lines (per batch: received/rejected/damaged)
      |                                    |
      +--------(lot_allocations)----- auction_lot (sold kg x price, per batch)

Every farmer's delivery can be followed to the exact kilograms sold and the price,
without ever modifying the original delivery record.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.delivery import Delivery
from app.models.reference import CollectionCentre, Crop, CropGrade, Season, Warehouse
from app.models.user import User

WEIGHT = Numeric(12, 3)
PRICE = Numeric(12, 4)
MONEY = Numeric(14, 2)


class AggregationBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "aggregation_batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "batch_no"),
        CheckConstraint("status IN ('open','closed','dispatched','received','partially_sold','sold')", name="status_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(40), nullable=False)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False)
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_centres.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    # Snapshot taken when the batch is closed: sum of member deliveries' net weight
    total_net_weight: Mapped[Decimal | None] = mapped_column(WEIGHT)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    crop: Mapped[Crop] = relationship()
    season: Mapped[Season] = relationship()
    centre: Mapped[CollectionCentre] = relationship()
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    members: Mapped[list["BatchDelivery"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class BatchDelivery(Base):
    """Membership of a delivery in a batch. delivery_id is UNIQUE: a delivery can be in only one batch."""

    __tablename__ = "batch_deliveries"

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregation_batches.id", ondelete="CASCADE"), primary_key=True)
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id", ondelete="RESTRICT"), primary_key=True, unique=True)
    net_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)  # snapshot at time of adding
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    batch: Mapped[AggregationBatch] = relationship(back_populates="members")
    delivery: Mapped[Delivery] = relationship()


class WarehouseDispatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warehouse_dispatches"
    __table_args__ = (
        UniqueConstraint("organization_id", "dispatch_no"),
        CheckConstraint("status IN ('in_transit','received')", name="status_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    dispatch_no: Mapped[str] = mapped_column(String(40), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    dispatch_date: Mapped[date] = mapped_column(Date, nullable=False)
    vehicle_reg: Mapped[str | None] = mapped_column(String(30))
    driver_name: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_transit", server_default="in_transit")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    warehouse: Mapped[Warehouse] = relationship()
    lines: Mapped[list["DispatchBatch"]] = relationship(back_populates="dispatch", cascade="all, delete-orphan")
    receipt: Mapped["WarehouseReceipt | None"] = relationship(back_populates="dispatch")


class DispatchBatch(Base):
    """A batch loaded on a dispatch, with the weight measured at loading."""

    __tablename__ = "dispatch_batches"
    __table_args__ = (CheckConstraint("dispatched_weight > 0", name="weight_positive"),)

    dispatch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouse_dispatches.id", ondelete="CASCADE"), primary_key=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregation_batches.id", ondelete="RESTRICT"), primary_key=True, unique=True)
    dispatched_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)

    dispatch: Mapped[WarehouseDispatch] = relationship(back_populates="lines")
    batch: Mapped[AggregationBatch] = relationship()


class WarehouseReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The warehouse's acknowledgement of a dispatch (one receipt per dispatch)."""

    __tablename__ = "warehouse_receipts"
    __table_args__ = (UniqueConstraint("warehouse_id", "receipt_no"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouse_dispatches.id", ondelete="RESTRICT"), nullable=False, unique=True)
    receipt_no: Mapped[str] = mapped_column(String(60), nullable=False)  # number on the warehouse's document
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    dispatch: Mapped[WarehouseDispatch] = relationship(back_populates="receipt")
    warehouse: Mapped[Warehouse] = relationship()
    lines: Mapped[list["WarehouseReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class WarehouseReceiptLine(UUIDPrimaryKeyMixin, Base):
    """Per-batch quantities at the warehouse. accepted = received - rejected - damaged."""

    __tablename__ = "warehouse_receipt_lines"
    __table_args__ = (
        CheckConstraint("received_weight >= 0 AND rejected_weight >= 0 AND damaged_weight >= 0", name="weights_not_negative"),
        CheckConstraint("accepted_weight = received_weight - rejected_weight - damaged_weight", name="accepted_formula"),
        CheckConstraint("accepted_weight >= 0", name="accepted_not_negative"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("warehouse_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregation_batches.id", ondelete="RESTRICT"), nullable=False, unique=True)
    received_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    rejected_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False, default=Decimal("0"), server_default="0")
    damaged_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False, default=Decimal("0"), server_default="0")
    accepted_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)

    receipt: Mapped[WarehouseReceipt] = relationship(back_populates="lines")
    batch: Mapped[AggregationBatch] = relationship()


class Discrepancy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A weight difference between two stages. Flagged automatically, resolved by an authorized user.
    Resolving NEVER changes farmer delivery records."""

    __tablename__ = "discrepancies"
    __table_args__ = (
        UniqueConstraint("batch_id", "stage"),
        CheckConstraint("stage IN ('batch_to_dispatch','dispatch_to_warehouse','warehouse_rejections')", name="stage_valid"),
        CheckConstraint("status IN ('open','explained','accepted')", name="status_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregation_batches.id", ondelete="RESTRICT"), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    actual_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    difference: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)  # actual - expected (negative = loss)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    explanation: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[AggregationBatch] = relationship()


class Auction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "auctions"
    __table_args__ = (
        UniqueConstraint("organization_id", "auction_ref"),
        CheckConstraint("status IN ('draft','approved')", name="status_valid"),
        CheckConstraint("approved_by IS NULL OR approved_by <> created_by", name="approver_differs"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    auction_ref: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g. the auction/exchange sale reference
    auction_date: Mapped[date] = mapped_column(Date, nullable=False)
    venue: Mapped[str | None] = mapped_column(String(150))
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    crop: Mapped[Crop] = relationship()
    season: Mapped[Season] = relationship()
    lots: Mapped[list["AuctionLot"]] = relationship(back_populates="auction", cascade="all, delete-orphan",
                                                    order_by="AuctionLot.lot_no")


class AuctionLot(UUIDPrimaryKeyMixin, Base):
    """One sale line: a quantity from ONE batch sold at ONE price. Different lots/grades may have different prices."""

    __tablename__ = "auction_lots"
    __table_args__ = (
        UniqueConstraint("auction_id", "lot_no"),
        CheckConstraint("quantity_sold > 0", name="qty_positive"),
        CheckConstraint("price_per_kg > 0", name="price_positive"),
        CheckConstraint("total_value = round(quantity_sold * price_per_kg, 2)", name="value_formula"),
    )

    auction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregation_batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    lot_no: Mapped[str] = mapped_column(String(40), nullable=False)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crop_grades.id", ondelete="RESTRICT"))
    quantity_sold: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    buyer: Mapped[str | None] = mapped_column(String(150))

    auction: Mapped[Auction] = relationship(back_populates="lots")
    batch: Mapped[AggregationBatch] = relationship()
    grade: Mapped[CropGrade | None] = relationship()
    allocations: Mapped[list["LotAllocation"]] = relationship(back_populates="lot", cascade="all, delete-orphan")


class LotAllocation(UUIDPrimaryKeyMixin, Base):
    """Each farmer delivery's share of an auction lot, computed when the auction is approved.

    Two weights are stored so the payout run can choose the loss policy explicitly:
    - weight_shared:   lot_qty x (delivery_net / batch_delivered)
                       -> warehouse losses reduce every farmer's paid kg proportionally.
    - weight_absorbed: lot_qty x (delivery_net / batch_accepted)
                       -> when the whole batch is sold, each farmer is paid on their full
                          delivered kg; the AMCOS bears the warehouse loss.
    """

    __tablename__ = "lot_allocations"
    __table_args__ = (
        UniqueConstraint("lot_id", "delivery_id"),
        CheckConstraint("weight_shared >= 0 AND weight_absorbed >= 0", name="weights_not_negative"),
    )

    lot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auction_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id", ondelete="RESTRICT"), nullable=False, index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True)
    weight_shared: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    weight_absorbed: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(PRICE, nullable=False)  # copied from the lot for traceability

    lot: Mapped[AuctionLot] = relationship(back_populates="allocations")
    delivery: Mapped[Delivery] = relationship()
