"""Deductions, input loans, payout runs and payments.

Money is NUMERIC(14,2) (exact decimals). Rates are NUMERIC(14,4).
Approved financial records are never edited: recalculation happens only on
unapproved runs; a paid payment can only be REVERSED (a new status with a reason).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.farmer import Farmer
from app.models.reference import Crop, Season
from app.models.user import User

MONEY = Numeric(14, 2)
RATE = Numeric(14, 4)
WEIGHT = Numeric(12, 3)


class DeductionType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configurable levy or other deduction. Nothing about rates is hardcoded."""

    __tablename__ = "deduction_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        CheckConstraint("calc_method IN ('percent_of_gross','per_kg','fixed')", name="method_valid"),
        CheckConstraint("applies_per IN ('farmer','delivery')", name="applies_valid"),
        CheckConstraint("category IN ('levy','other')", name="category_valid"),
        CheckConstraint("rate >= 0", name="rate_not_negative"),
        CheckConstraint("calc_method <> 'percent_of_gross' OR rate <= 100", name="percent_max_100"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="dates_ordered"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(10), nullable=False, default="levy")
    calc_method: Mapped[str] = mapped_column(String(20), nullable=False)
    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    # 'fixed' amounts apply once per farmer per run, or once per delivery included
    applies_per: Mapped[str] = mapped_column(String(10), nullable=False, default="farmer", server_default="farmer")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")  # lower = first
    crop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"))      # NULL = all crops
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))  # NULL = all seasons
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    description: Mapped[str | None] = mapped_column(Text)

    crop: Mapped[Crop | None] = relationship()
    season: Mapped[Season | None] = relationship()


class InputLoan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An agricultural input loan/advance, repaid from produce payments (or cash)."""

    __tablename__ = "input_loans"
    __table_args__ = (
        UniqueConstraint("organization_id", "loan_ref"),
        CheckConstraint("principal > 0", name="principal_positive"),
        CheckConstraint("max_deduction_percent IS NULL OR (max_deduction_percent > 0 AND max_deduction_percent <= 100)", name="cap_valid"),
        CheckConstraint("status IN ('active','repaid','written_off')", name="status_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True)
    loan_ref: Mapped[str] = mapped_column(String(40), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)  # e.g. "Sulphur dust 4 bags"
    principal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Max share of a payout's remaining amount that may go to this loan (protects farmer income)
    max_deduction_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    terms: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    farmer: Mapped[Farmer] = relationship()
    repayments: Mapped[list["LoanRepayment"]] = relationship(back_populates="loan", order_by="LoanRepayment.repayment_date")

    @property
    def repaid(self) -> Decimal:
        return sum((r.amount for r in self.repayments if not r.reversed), Decimal("0"))

    @property
    def outstanding(self) -> Decimal:
        # Computed, never stored: avoids the balance drifting from the repayment history.
        return self.principal - self.repaid


class LoanRepayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loan_repayments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("source IN ('payout','cash')", name="source_valid"),
    )

    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("input_loans.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    farmer_payout_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmer_payouts.id", ondelete="RESTRICT"))
    repayment_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(60))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reversed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    loan: Mapped[InputLoan] = relationship(back_populates="repayments")


class PayoutRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One calculation of farmer payouts for a crop + season, under an explicit loss policy."""

    __tablename__ = "payout_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "run_no"),
        CheckConstraint("status IN ('calculated','approved','cancelled')", name="status_valid"),
        CheckConstraint("loss_policy IN ('shared','absorbed')", name="policy_valid"),
        CheckConstraint("approved_by IS NULL OR approved_by <> calculated_by", name="approver_differs"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    run_no: Mapped[str] = mapped_column(String(40), nullable=False)
    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"), nullable=False)
    loss_policy: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="calculated", server_default="calculated")
    calculated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    total_gross: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    total_net: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)

    crop: Mapped[Crop] = relationship()
    season: Mapped[Season] = relationship()
    payouts: Mapped[list["FarmerPayout"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class PayoutRunAllocation(Base):
    """Which lot allocations a run pays for. allocation_id is UNIQUE: an allocation can be
    in only one live run, so the same sold kilograms can never be paid twice.
    Rows are deleted when a run is cancelled, releasing the allocations."""

    __tablename__ = "payout_run_allocations"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payout_runs.id", ondelete="CASCADE"), primary_key=True)
    allocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lot_allocations.id", ondelete="RESTRICT"),
                                                     primary_key=True, unique=True)


class FarmerPayout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farmer_payouts"
    __table_args__ = (
        UniqueConstraint("run_id", "farmer_id"),
        CheckConstraint("status IN ('calculated','approved','needs_review','paid','cancelled')", name="status_valid"),
        CheckConstraint("net_payable >= 0", name="net_not_negative"),
        CheckConstraint("gross_amount >= 0 AND total_deductions >= 0", name="amounts_not_negative"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payout_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True)
    eligible_weight: Mapped[Decimal] = mapped_column(WEIGHT, nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_payable: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Positive when levies exceed gross: the payout is held for review, never paid negative.
    shortfall: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"), server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="calculated", server_default="calculated")
    flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")

    run: Mapped[PayoutRun] = relationship(back_populates="payouts")
    farmer: Mapped[Farmer] = relationship()
    lines: Mapped[list["PayoutLine"]] = relationship(back_populates="payout", cascade="all, delete-orphan",
                                                     order_by="PayoutLine.sort_order")


class PayoutLine(UUIDPrimaryKeyMixin, Base):
    """Itemized explanation of a payout. Earnings are positive; deductions are stored as
    positive amounts with line_type levy/loan/other. sum(earnings) - sum(deductions) = net (+ shortfall)."""

    __tablename__ = "payout_lines"
    __table_args__ = (
        CheckConstraint("line_type IN ('earning','levy','loan','other')", name="type_valid"),
        CheckConstraint("amount >= 0", name="amount_not_negative"),
    )

    farmer_payout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmer_payouts.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    line_type: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(WEIGHT)  # kg, for earning and per-kg lines
    rate: Mapped[Decimal | None] = mapped_column(RATE)        # price/kg, %, per-kg rate or fixed amount
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    lot_allocation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lot_allocations.id", ondelete="RESTRICT"))
    deduction_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deduction_types.id", ondelete="RESTRICT"))
    loan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("input_loans.id", ondelete="RESTRICT"))

    payout: Mapped[FarmerPayout] = relationship(back_populates="lines")


class PaymentBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A group of farmer payments sent through one channel. Maker-checker enforced by the DB."""

    __tablename__ = "payment_batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "batch_no"),
        CheckConstraint("method IN ('mobile_money','bank','cash')", name="method_valid"),
        CheckConstraint("status IN ('draft','awaiting_approval','approved','exported','partially_completed','paid','failed','cancelled')", name="status_valid"),
        CheckConstraint("approved_by IS NULL OR approved_by <> prepared_by", name="approver_differs"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(40), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    prepared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    export_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)

    preparer: Mapped[User] = relationship(foreign_keys=[prepared_by])
    payments: Mapped[list["Payment"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("status IN ('pending','exported','paid','failed','reversed')", name="status_valid"),
        CheckConstraint("status <> 'paid' OR transaction_ref IS NOT NULL", name="paid_has_reference"),
        # THE duplicate-payment guard: a payout can have at most one payment that is not failed/reversed.
        Index("uq_payments_live_per_payout", "farmer_payout_id", unique=True,
              postgresql_where=text("status NOT IN ('failed','reversed')")),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_payout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmer_payouts.id", ondelete="RESTRICT"), nullable=False, index=True)
    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Snapshot of where the money is sent, as it was when the batch was prepared
    destination: Mapped[str | None] = mapped_column(String(60))
    destination_bank: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    transaction_ref: Mapped[str | None] = mapped_column(String(100))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[PaymentBatch] = relationship(back_populates="payments")
    farmer: Mapped[Farmer] = relationship()
    payout: Mapped[FarmerPayout] = relationship()
