"""The AMCOS (cooperative). Almost every other table points to it (multi-tenancy)."""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Short code used as prefix in receipt numbers, e.g. "MTW" -> MTW-2026-000123
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(100), unique=True)
    region: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    logo_path: Mapped[str | None] = mapped_column(String(300))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TZS", server_default="TZS")
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Africa/Dar_es_Salaam", server_default="Africa/Dar_es_Salaam"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # True for records created by the development seed script — never in production.
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
