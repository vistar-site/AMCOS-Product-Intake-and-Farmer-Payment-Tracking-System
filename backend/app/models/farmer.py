"""Farmers (cooperative members)."""
import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.reference import CollectionCentre


class Farmer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farmers"
    __table_args__ = (
        # A membership number is unique inside one AMCOS (two AMCOS may both have "M-001").
        UniqueConstraint("organization_id", "membership_no"),
        CheckConstraint("status IN ('active', 'inactive', 'suspended')", name="status_valid"),
        CheckConstraint("gender IS NULL OR gender IN ('female', 'male', 'other')", name="gender_valid"),
        CheckConstraint(
            "payment_method IN ('mobile_money', 'bank', 'cash')", name="payment_method_valid"
        ),
        # Case-insensitive name search: an index on lower(full_name).
        Index("ix_farmers_lower_full_name", text("lower(full_name)")),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    home_centre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collection_centres.id", ondelete="RESTRICT"), index=True
    )
    membership_no: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), index=True)  # E.164, e.g. +255712345678
    gender: Mapped[str | None] = mapped_column(String(10))
    village: Mapped[str | None] = mapped_column(String(100), index=True)
    ward: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    registration_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")

    # Payment details (needed in Phase 7). Never cached on offline devices.
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="mobile_money", server_default="mobile_money"
    )
    mobile_money_number: Mapped[str | None] = mapped_column(String(20))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account_no: Mapped[str | None] = mapped_column(String(50))

    notes: Mapped[str | None] = mapped_column(Text)
    # Cooperative-configurable identification fields (e.g. NIDA number) without schema changes.
    extra_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    home_centre: Mapped[CollectionCentre | None] = relationship()
