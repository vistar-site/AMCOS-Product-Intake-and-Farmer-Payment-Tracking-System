import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PHONE = r"^\+?[0-9]{9,15}$"


class CentreMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class FarmerRead(BaseModel):
    """Visible to anyone with farmer.view. No payment details."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    membership_no: str
    full_name: str
    phone: str | None
    gender: str | None
    village: str | None
    ward: str | None
    district: str | None
    region: str | None
    home_centre: CentreMini | None
    registration_date: date
    status: str
    notes: str | None
    extra_fields: dict
    created_at: datetime


class FarmerFinancialRead(FarmerRead):
    """Adds payment details — only for users holding farmer.view_financial."""
    payment_method: str
    mobile_money_number: str | None
    bank_name: str | None
    bank_account_no: str | None


class _FarmerFields(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    phone: str | None = Field(None, pattern=PHONE)
    gender: str | None = Field(None, pattern="^(female|male|other)$")
    village: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    home_centre_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)
    extra_fields: dict = {}


class FarmerCreate(_FarmerFields):
    # Optional: if omitted, the system assigns the next number (e.g. DEMO-0013)
    membership_no: str | None = Field(None, min_length=1, max_length=50, pattern=r"^[A-Za-z0-9/_-]+$")
    registration_date: date | None = None
    payment_method: str = Field("mobile_money", pattern="^(mobile_money|bank|cash)$")
    mobile_money_number: str | None = Field(None, pattern=PHONE)
    bank_name: str | None = Field(None, max_length=100)
    bank_account_no: str | None = Field(None, max_length=50)

    @model_validator(mode="after")
    def payment_details(self):
        if self.payment_method == "bank" and not (self.bank_name and self.bank_account_no):
            raise ValueError("Bank name and account number are required for bank payments")
        return self


class FarmerUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=3, max_length=200)
    phone: str | None = Field(None, pattern=PHONE)
    gender: str | None = Field(None, pattern="^(female|male|other)$")
    village: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    home_centre_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)
    extra_fields: dict | None = None
    payment_method: str | None = Field(None, pattern="^(mobile_money|bank|cash)$")
    mobile_money_number: str | None = Field(None, pattern=PHONE)
    bank_name: str | None = Field(None, max_length=100)
    bank_account_no: str | None = Field(None, max_length=50)


class FarmerStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|inactive|suspended)$")
    reason: str = Field(min_length=3, max_length=500)


class FarmerCropSummary(BaseModel):
    crop_code: str
    crop_name: str
    deliveries: int
    net_weight: Decimal


class FarmerSummary(BaseModel):
    total_deliveries: int
    total_net_weight: Decimal
    last_delivery_at: datetime | None
    by_crop: list[FarmerCropSummary]
