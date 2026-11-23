"""SMS templates and the message log (which doubles as the send/retry queue)."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.farmer import Farmer


class SmsTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Editable message text with {placeholders}, one per event and language."""

    __tablename__ = "sms_templates"
    __table_args__ = (UniqueConstraint("organization_id", "code", "language"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)       # e.g. DELIVERY_RECEIPT
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="sw")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")


class SmsMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every SMS the system tried to send. Status flow:
    queued -> sent -> delivered        (provider confirmed)
    queued -> failed -> queued (retry) ... until max attempts
    'simulated' = handled by the MOCK provider: nothing was actually sent to a phone."""

    __tablename__ = "sms_messages"
    __table_args__ = (
        CheckConstraint("status IN ('queued','sent','delivered','failed','simulated','cancelled')", name="status_valid"),
        Index("ix_sms_messages_status_next", "status", "next_attempt_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    farmer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farmers.id", ondelete="RESTRICT"), index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String(30))  # delivery / payment
    related_id: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(30))
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    farmer: Mapped[Farmer | None] = relationship()
