"""Farmer SMS notifications.

Two steps, on purpose:
 1. enqueue_*()   — called INSIDE the business transaction (delivery saved, payment confirmed).
                    It only inserts an sms_messages row with status 'queued'. If the business
                    transaction rolls back, the message disappears with it: no SMS for a
                    delivery that was never saved.
 2. process_queue() — called AFTER the commit (FastAPI background task, or the "Send queued"
                    button). Talks to the provider. A provider outage therefore never blocks or
                    breaks recording a delivery; failed messages are retried with backoff.
"""
import logging
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.integrations.sms.base import SendResult
from app.integrations.sms.mock import get_provider
from app.models import Delivery, Farmer, Organization, Payment, SmsMessage, SmsTemplate, User
from app.services import audit_service
from app.services.settings_service import get_setting

log = logging.getLogger(__name__)

# Default texts (Swahili first, English alternative). AMCOS admins can edit them.
DEFAULT_TEMPLATES: dict[tuple[str, str], str] = {
    ("DELIVERY_RECEIPT", "sw"): "{org}: Tumepokea {crop} kg {net} kutoka kwa {farmer} ({member}) {date}. Risiti {receipt}. Asante.",
    ("DELIVERY_RECEIPT", "en"): "{org}: Received {net} kg {crop} from {farmer} ({member}) on {date}. Receipt {receipt}. Thank you.",
    ("PAYMENT_CONFIRMED", "sw"): "{org}: Malipo ya TZS {amount} yametumwa kwa {farmer}. Kumbukumbu {ref}. Asante.",
    ("PAYMENT_CONFIRMED", "en"): "{org}: Payment of TZS {amount} has been sent to {farmer}. Reference {ref}. Thank you.",
}
PLACEHOLDERS = {
    "DELIVERY_RECEIPT": ["org", "farmer", "member", "crop", "net", "date", "receipt"],
    "PAYMENT_CONFIRMED": ["org", "farmer", "amount", "ref"],
}


class _SafeDict(dict):
    def __missing__(self, key):  # unknown placeholder -> left visible, never crashes
        return "{" + key + "}"


def _template(db: Session, org: uuid.UUID, code: str, lang: str) -> str:
    t = db.scalar(select(SmsTemplate).where(SmsTemplate.organization_id == org, SmsTemplate.code == code,
                                            SmsTemplate.language == lang, SmsTemplate.is_active.is_(True)))
    return t.body if t else DEFAULT_TEMPLATES[(code, lang)]


def _enabled(db: Session, org: uuid.UUID, key: str) -> bool:
    return bool(get_setting(db, org, "sms.enabled")) and bool(get_setting(db, org, key))


def _enqueue(db: Session, org: uuid.UUID, farmer: Farmer, code: str, values: dict, related_type: str, related_id) -> SmsMessage | None:
    if not farmer.phone:
        return None
    lang = get_setting(db, org, "sms.language")
    body = _template(db, org, code, lang).format_map(_SafeDict(values))[:480]
    msg = SmsMessage(organization_id=org, farmer_id=farmer.id, phone=farmer.phone, template_code=code, body=body,
                     related_type=related_type, related_id=str(related_id), status="queued",
                     next_attempt_at=datetime.now(UTC))
    db.add(msg)
    return msg


def enqueue_delivery_receipt(db: Session, delivery: Delivery) -> None:
    org = db.get(Organization, delivery.organization_id)
    if not _enabled(db, org.id, "sms.delivery_receipt"):
        return
    when = delivery.captured_at.astimezone(ZoneInfo(org.timezone)).strftime("%d/%m/%Y %H:%M")
    _enqueue(db, org.id, delivery.farmer, "DELIVERY_RECEIPT", {
        "org": org.name[:30], "farmer": delivery.farmer.full_name, "member": delivery.farmer.membership_no,
        "crop": delivery.crop.name, "net": f"{delivery.net_weight:,.1f}", "date": when, "receipt": delivery.receipt_no,
    }, "delivery", delivery.id)


def enqueue_payment_confirmation(db: Session, payment: Payment) -> None:
    org = db.get(Organization, payment.batch.organization_id)
    if not _enabled(db, org.id, "sms.payment_confirmation"):
        return
    _enqueue(db, org.id, payment.farmer, "PAYMENT_CONFIRMED", {
        "org": org.name[:30], "farmer": payment.farmer.full_name, "amount": f"{payment.amount:,.0f}",
        "ref": payment.transaction_ref or "",
    }, "payment", payment.id)


def process_queue(db: Session, organization_id: uuid.UUID | None = None, limit: int = 100) -> dict:
    """Send due messages. Safe to call repeatedly; each message is claimed with SKIP LOCKED
    so two workers never send the same SMS twice."""
    provider = get_provider(get_settings().sms_provider)
    now = datetime.now(UTC)
    stmt = (select(SmsMessage).where(SmsMessage.status == "queued",
                                     or_(SmsMessage.next_attempt_at.is_(None), SmsMessage.next_attempt_at <= now))
            .order_by(SmsMessage.created_at).limit(limit).with_for_update(skip_locked=True))
    if organization_id:
        stmt = stmt.where(SmsMessage.organization_id == organization_id)
    counts = {"sent": 0, "simulated": 0, "failed": 0, "retry": 0}
    for msg in db.scalars(stmt):
        msg.attempts += 1
        msg.provider = provider.name
        try:
            res = provider.send(msg.phone, msg.body)
        except Exception as exc:  # provider bug/outage must never crash the loop
            log.exception("SMS provider error")
            res = SendResult(ok=False, status="failed", error=str(exc)[:300])
        if res.ok:
            msg.status, msg.provider_message_id, msg.sent_at, msg.last_error = res.status, res.provider_message_id, now, None
            counts[res.status if res.status in counts else "sent"] += 1
        else:
            msg.last_error = res.error
            max_attempts = int(get_setting(db, msg.organization_id, "sms.max_attempts"))
            if res.retryable and msg.attempts < max_attempts:
                msg.status = "queued"
                msg.next_attempt_at = now + timedelta(minutes=5 * 2 ** (msg.attempts - 1))  # 5, 10, 20 min…
                counts["retry"] += 1
            else:
                msg.status = "failed"
                counts["failed"] += 1
    db.commit()
    return counts


def process_queue_background(organization_id: uuid.UUID) -> None:
    """Entry point for FastAPI BackgroundTasks: uses its own session (the request's is closed)."""
    from app.database.session import SessionLocal
    with SessionLocal() as db:
        try:
            process_queue(db, organization_id)
        except Exception:
            log.exception("Background SMS processing failed")


# ---------------- admin operations
def list_messages(db: Session, org: uuid.UUID, *, status, farmer_id, q, page, page_size):
    from sqlalchemy import func
    stmt = select(SmsMessage).where(SmsMessage.organization_id == org)
    if status:
        stmt = stmt.where(SmsMessage.status == status)
    if farmer_id:
        stmt = stmt.where(SmsMessage.farmer_id == farmer_id)
    if q:
        stmt = stmt.where(or_(SmsMessage.phone.contains(q), SmsMessage.body.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(SmsMessage.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(items), total


def retry_message(db: Session, actor: User, org: uuid.UUID, message_id: uuid.UUID) -> SmsMessage:
    m = db.get(SmsMessage, message_id)
    if m is None or m.organization_id != org:
        raise NotFoundError("Message not found")
    if m.status != "failed":
        raise ValidationFailedError("Only failed messages can be retried")
    m.status, m.next_attempt_at, m.attempts = "queued", datetime.now(UTC), 0
    audit_service.record(db, action="sms.retry", user_id=actor.id, organization_id=org, entity_type="sms", entity_id=m.id)
    db.commit()
    return m


def list_templates(db: Session, org: uuid.UUID) -> list[dict]:
    stored = {(t.code, t.language): t for t in db.scalars(select(SmsTemplate).where(SmsTemplate.organization_id == org))}
    out = []
    for (code, lang), default in DEFAULT_TEMPLATES.items():
        t = stored.get((code, lang))
        out.append({"code": code, "language": lang, "body": t.body if t else default, "is_default": t is None,
                    "placeholders": PLACEHOLDERS[code]})
    return out


def save_template(db: Session, actor: User, org: uuid.UUID, code: str, lang: str, body: str) -> list[dict]:
    if (code, lang) not in DEFAULT_TEMPLATES:
        raise NotFoundError("Unknown template")
    import string
    used = {f for _, f, _, _ in string.Formatter().parse(body) if f}
    bad = used - set(PLACEHOLDERS[code])
    if bad:
        raise ValidationFailedError(f"Unknown placeholder(s): {', '.join(sorted(bad))}")
    t = db.scalar(select(SmsTemplate).where(SmsTemplate.organization_id == org, SmsTemplate.code == code,
                                            SmsTemplate.language == lang))
    old = t.body if t else DEFAULT_TEMPLATES[(code, lang)]
    if t:
        t.body = body
    else:
        db.add(SmsTemplate(organization_id=org, code=code, language=lang, body=body))
    audit_service.record(db, action="sms.template_update", user_id=actor.id, organization_id=org,
                         entity_type="sms_template", entity_id=f"{code}:{lang}", before={"body": old}, after={"body": body})
    db.commit()
    return list_templates(db, org)
