"""Configurable reference data: seasons, crops, grades, collection centres, warehouses.

Nothing here is hardcoded in code — each AMCOS configures its own rows.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import user_centres

ACTIVE_STATUSES = "status IN ('active', 'inactive')"


class Season(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2026/27"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Crop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crops"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "CASHEW"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="kg", server_default="kg")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Crop-specific operational rules, e.g. {"max_tare_kg": 2, "max_gross_kg": 500}
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    grades: Mapped[list["CropGrade"]] = relationship(back_populates="crop", cascade="all, delete-orphan")


class CropGrade(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "crop_grades"
    __table_args__ = (UniqueConstraint("crop_id", "code"),)

    crop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crops.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "STD", "UG"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    crop: Mapped[Crop] = relationship(back_populates="grades")


class CollectionCentre(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_centres"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        CheckConstraint(ACTIVE_STATUSES, name="status_valid"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    village: Mapped[str | None] = mapped_column(String(100))
    ward: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        secondary=user_centres, back_populates="centres"
    )


class Warehouse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(150))
    licence_no: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
