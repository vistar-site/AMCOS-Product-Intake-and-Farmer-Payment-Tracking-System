"""Pydantic schemas: the exact shape of data entering (Create/Update) and leaving (Read) the API.

Read schemas deliberately omit password_hash: the hash can never leak through the API
because it is not a field of any response model.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # allows building from ORM objects
    id: uuid.UUID
    code: str
    name: str


class CentreRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID | None
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    locked_until: datetime | None
    created_at: datetime
    roles: list[RoleRead]
    centres: list[CentreRef]


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{9,15}$")
    temporary_password: str = Field(min_length=10, max_length=200)
    role_codes: list[str] = Field(min_length=1)
    centre_ids: list[uuid.UUID] = []
    organization_id: uuid.UUID | None = None  # only system admins may set this


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{9,15}$")
    role_codes: list[str] | None = Field(default=None, min_length=1)
    centre_ids: list[uuid.UUID] | None = None


class UserStatusUpdate(BaseModel):
    is_active: bool
    reason: str = Field(min_length=3, max_length=500)
