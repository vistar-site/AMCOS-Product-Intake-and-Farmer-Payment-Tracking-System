import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MONEY = dict(max_digits=14, decimal_places=2)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NameRef(ORM):
    id: uuid.UUID
    name: str


class FarmerMini(ORM):
    id: uuid.UUID
    full_name: str
    membership_no: str


# ---------------- Deductions
class DeductionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)
    category: Literal["levy", "other"] = "levy"
    calc_method: Literal["percent_of_gross", "per_kg", "fixed"]
    rate: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    applies_per: Literal["farmer", "delivery"] = "farmer"
    priority: int = Field(100, ge=0, le=10000)
    crop_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    effective_from: date
    effective_to: date | None = None
    description: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def check(self):
        if self.calc_method == "percent_of_gross" and self.rate > 100:
            raise ValueError("A percentage cannot exceed 100")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class DeductionUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    rate: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=4)
    priority: int | None = Field(None, ge=0, le=10000)
    effective_to: date | None = None
    is_active: bool | None = None
    description: str | None = Field(None, max_length=1000)


class DeductionRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    category: str
    calc_method: str
    rate: Decimal
    applies_per: str
    priority: int
    crop: NameRef | None
    season: NameRef | None
    effective_from: date
    effective_to: date | None
    is_active: bool
    description: str | None


# ---------------- Loans
class LoanCreate(BaseModel):
    farmer_id: uuid.UUID
    loan_ref: str | None = Field(None, max_length=40)
    issue_date: date
    description: str = Field(min_length=3, max_length=300)
    principal: Decimal = Field(gt=0, **MONEY)
    max_deduction_percent: Decimal | None = Field(None, gt=0, le=100, max_digits=5, decimal_places=2)
    terms: str | None = Field(None, max_length=2000)


class RepaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, **MONEY)
    repayment_date: date
    reference: str | None = Field(None, max_length=60)


class RepaymentRead(ORM):
    id: uuid.UUID
    amount: Decimal
    source: str
    repayment_date: date
    reference: str | None
    reversed: bool


class LoanRead(ORM):
    id: uuid.UUID
    loan_ref: str
    farmer: FarmerMini
    issue_date: date
    description: str
    principal: Decimal
    max_deduction_percent: Decimal | None
    terms: str | None
    status: str
    repaid: Decimal
    outstanding: Decimal
    repayments: list[RepaymentRead]


# ---------------- Payouts
class RunCreate(BaseModel):
    crop_id: uuid.UUID
    season_id: uuid.UUID
    loss_policy: Literal["shared", "absorbed"]
    notes: str | None = Field(None, max_length=1000)


class ReasonBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class PayoutLineRead(ORM):
    sort_order: int
    line_type: str
    description: str
    quantity: Decimal | None
    rate: Decimal | None
    amount: Decimal


class FarmerPayoutRead(ORM):
    id: uuid.UUID
    farmer: FarmerMini
    eligible_weight: Decimal
    gross_amount: Decimal
    total_deductions: Decimal
    net_payable: Decimal
    shortfall: Decimal
    status: str
    flags: list[str]
    lines: list[PayoutLineRead]


class RunSummary(ORM):
    id: uuid.UUID
    run_no: str
    crop: NameRef
    season: NameRef
    loss_policy: str
    status: str
    calculated_by: uuid.UUID
    calculated_at: datetime
    approved_at: datetime | None
    cancelled_reason: str | None
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
    notes: str | None


class RunRead(RunSummary):
    payouts: list[FarmerPayoutRead]


# ---------------- Payments
class EligiblePayout(BaseModel):
    payout_id: uuid.UUID
    run_no: str
    farmer: FarmerMini
    net_payable: Decimal
    problem: str | None


class PaymentBatchCreate(BaseModel):
    method: Literal["mobile_money", "bank", "cash"]
    payout_ids: list[uuid.UUID] = Field(min_length=1, max_length=5000)
    notes: str | None = Field(None, max_length=1000)


class PaymentRead(ORM):
    id: uuid.UUID
    farmer: FarmerMini
    farmer_payout_id: uuid.UUID
    amount: Decimal
    destination: str | None
    destination_bank: str | None
    status: str
    transaction_ref: str | None
    paid_at: datetime | None
    failure_reason: str | None


class UserMini(ORM):
    id: uuid.UUID
    full_name: str


class PaymentBatchRead(ORM):
    id: uuid.UUID
    batch_no: str
    method: str
    status: str
    preparer: UserMini
    prepared_by: uuid.UUID
    approved_by: uuid.UUID | None
    submitted_at: datetime | None
    approved_at: datetime | None
    exported_at: datetime | None
    export_count: int
    notes: str | None
    created_at: datetime
    payments: list[PaymentRead]


class PaymentResult(BaseModel):
    payment_id: uuid.UUID
    status: Literal["paid", "failed"]
    transaction_ref: str | None = Field(None, max_length=100)
    failure_reason: str | None = Field(None, max_length=500)
    paid_at: datetime | None = None


class ResultsBody(BaseModel):
    results: list[PaymentResult] = Field(min_length=1)


# ---------------- Statement
class StatementDelivery(ORM):
    id: uuid.UUID
    receipt_no: str
    captured_at: datetime
    crop: NameRef
    centre: NameRef
    net_weight: Decimal
    status: str


class StatementPayout(ORM):
    id: uuid.UUID
    run: RunSummary
    eligible_weight: Decimal
    gross_amount: Decimal
    total_deductions: Decimal
    net_payable: Decimal
    status: str
    flags: list[str]
    lines: list[PayoutLineRead]


class StatementPayment(ORM):
    id: uuid.UUID
    amount: Decimal
    status: str
    transaction_ref: str | None
    paid_at: datetime | None
    failure_reason: str | None
    created_at: datetime


class Statement(BaseModel):
    farmer: FarmerMini
    deliveries: list[StatementDelivery]
    payouts: list[StatementPayout]
    payments: list[StatementPayment]
    loans: list[LoanRead]
    totals: dict[str, Decimal]
