"""Audit log, settings and number sequences."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(Base):
    """Append-only record of important operations. Never updated or deleted.

    Uses a BIGINT sequence key (not UUID) so rows have a strict insertion order.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    # SET NULL is never used: users are deactivated, not deleted, so RESTRICT is safe.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. "farmer.update"
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class Setting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Key/value settings per AMCOS, e.g. key='sms.delivery_receipt_enabled', value=true."""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict | list | str | int | bool | None] = mapped_column(JSONB)


class NumberSequence(Base):
    """Counters for human-readable numbers (receipts, batches).

    Read with SELECT ... FOR UPDATE inside a transaction so two clerks can
    never receive the same receipt number.
    """

    __tablename__ = "number_sequences"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    sequence_key: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "delivery:2026"
    next_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")
