import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

CODE = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Organization ---
class OrganizationRead(ORM):
    id: uuid.UUID
    name: str
    code: str
    registration_no: str | None
    region: str | None
    district: str | None
    address: str | None
    phone: str | None
    email: str | None
    currency: str
    timezone: str
    is_demo: bool


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    registration_no: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{9,15}$")
    email: EmailStr | None = None


# --- Centres ---
class StaffRef(ORM):
    id: uuid.UUID
    full_name: str
    email: str


class CentreRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    village: str | None
    ward: str | None
    district: str | None
    region: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    status: str
    users: list[StaffRef] = []


class CentreCreate(BaseModel):
    code: str = CODE
    name: str = Field(min_length=2, max_length=150)
    village: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)


class CentreUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
    village: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    district: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    status: str | None = Field(None, pattern="^(active|inactive)$")


class CentreStaffUpdate(BaseModel):
    user_ids: list[uuid.UUID]


# --- Crops ---
class GradeRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class GradeCreate(BaseModel):
    code: str = CODE
    name: str = Field(min_length=1, max_length=100)


class CropRules(BaseModel):
    """Configurable per-crop validation limits used at intake."""
    max_gross_kg: Decimal | None = Field(None, gt=0)
    max_tare_kg: Decimal | None = Field(None, ge=0)
    grade_required: bool = False


class CropRead(ORM):
    id: uuid.UUID
    code: str
    name: str
    unit: str
    is_active: bool
    rules: dict
    grades: list[GradeRead]


class CropCreate(BaseModel):
    code: str = CODE
    name: str = Field(min_length=2, max_length=100)
    unit: str = Field("kg", pattern="^(kg)$")  # only kg supported for now; see docs
    rules: CropRules = CropRules()
    grades: list[GradeCreate] = []


class CropUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    is_active: bool | None = None
    rules: CropRules | None = None


# --- Seasons ---
class SeasonRead(ORM):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    is_active: bool


class SeasonCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SeasonUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
