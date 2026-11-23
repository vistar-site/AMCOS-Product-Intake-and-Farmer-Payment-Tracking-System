"""Bulk payment batches.

Workflow:  draft --submit--> awaiting_approval --approve (different user)--> approved
           --export file--> exported --reconcile results--> partially_completed | paid | failed
Rules:
 - Only approved payouts with net > 0 and complete destination details can be added.
 - A payout can have only ONE live payment (DB partial unique index) -> no duplicate payments.
 - Exporting NEVER marks anything paid. Only recorded results (with a transaction reference) do.
 - A paid payment can only be REVERSED, with a reason; then the payout may be paid again.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.integrations.payments.base import PaymentInstruction
from app.integrations.payments.file_export import get_exporter
from app.models import Farmer, FarmerPayout, Organization, Payment, PaymentBatch, PayoutRun, User
from app.services import audit_service
from app.services.numbering import next_number
from app.services.scope import org_id

LIVE = ("pending", "exported", "paid")


def _options():
    return (selectinload(PaymentBatch.preparer),
            selectinload(PaymentBatch.payments).selectinload(Payment.farmer),
            selectinload(PaymentBatch.payments).selectinload(Payment.payout).selectinload(FarmerPayout.run))


def get_batch(db: Session, actor: User, batch_id: uuid.UUID) -> PaymentBatch:
    b = db.scalar(select(PaymentBatch).where(PaymentBatch.id == batch_id, PaymentBatch.organization_id == org_id(actor))
                  .options(*_options()))
    if b is None:
        raise NotFoundError("Payment batch not found")
    return b


def list_batches(db: Session, actor: User, status: str | None) -> list[PaymentBatch]:
    stmt = select(PaymentBatch).where(PaymentBatch.organization_id == org_id(actor)).options(*_options())
    if status:
        stmt = stmt.where(PaymentBatch.status == status)
    return list(db.scalars(stmt.order_by(PaymentBatch.created_at.desc())))


def destination_problem(farmer: Farmer, method: str) -> str | None:
    if farmer.payment_method != method:
        return f"farmer is set to be paid by {farmer.payment_method.replace('_', ' ')}"
    if method == "mobile_money" and not farmer.mobile_money_number:
        return "missing mobile money number"
    if method == "bank" and not (farmer.bank_name and farmer.bank_account_no):
        return "missing bank name or account number"
    return None


def eligible_payouts(db: Session, actor: User, method: str) -> list[dict]:
    """Approved payouts not yet (successfully) paid, with a warning if they can't use `method`."""
    live = select(Payment.farmer_payout_id).where(Payment.status.in_(LIVE))
    payouts = db.scalars(select(FarmerPayout).join(PayoutRun)
                         .where(PayoutRun.organization_id == org_id(actor), PayoutRun.status == "approved",
                                FarmerPayout.status == "approved", FarmerPayout.net_payable > 0,
                                FarmerPayout.id.not_in(live))
                         .options(selectinload(FarmerPayout.farmer), selectinload(FarmerPayout.run))
                         .order_by(FarmerPayout.created_at))
    return [{"payout": p, "problem": destination_problem(p.farmer, method)} for p in payouts]


def create_batch(db: Session, actor: User, method: str, payout_ids: list[uuid.UUID], notes: str | None) -> PaymentBatch:
    org = org_id(actor)
    eligible = {e["payout"].id: e for e in eligible_payouts(db, actor, method)}
    problems = []
    for pid in payout_ids:
        e = eligible.get(pid)
        if e is None:
            problems.append(f"{pid}: not eligible (not approved, already paid/in another batch, or nothing payable)")
        elif e["problem"]:
            problems.append(f"{e['payout'].farmer.full_name}: {e['problem']}")
    if problems:
        raise ValidationFailedError("Cannot add: " + "; ".join(problems[:10]))
    year = datetime.now(UTC).year
    batch = PaymentBatch(organization_id=org, method=method, prepared_by=actor.id, notes=notes,
                         batch_no=f"{db.get(Organization, org).code}-PAY{year}-{next_number(db, org, f'paybatch:{year}'):04d}")
    for pid in payout_ids:
        p = eligible[pid]["payout"]
        f = p.farmer
        batch.payments.append(Payment(
            farmer_payout_id=p.id, farmer_id=f.id, amount=p.net_payable,
            destination=f.mobile_money_number if method == "mobile_money" else f.bank_account_no if method == "bank" else None,
            destination_bank=f.bank_name if method == "bank" else None))
    db.add(batch)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("A selected payout was added to another batch at the same time") from exc
    audit_service.record(db, action="payment_batch.create", user_id=actor.id, organization_id=org,
                         entity_type="payment_batch", entity_id=batch.id,
                         after={"batch_no": batch.batch_no, "method": method, "payments": len(payout_ids),
                                "total": str(sum(p.amount for p in batch.payments))})
    db.commit()
    return get_batch(db, actor, batch.id)


def _transition(db: Session, actor: User, batch: PaymentBatch, action: str, to: str, **audit) -> PaymentBatch:
    audit_service.record(db, action=f"payment_batch.{action}", user_id=actor.id, organization_id=batch.organization_id,
                         entity_type="payment_batch", entity_id=batch.id, before={"status": batch.status},
                         after={"status": to}, **audit)
    batch.status = to
    db.commit()
    return get_batch(db, actor, batch.id)


def submit(db: Session, actor: User, batch_id: uuid.UUID) -> PaymentBatch:
    b = get_batch(db, actor, batch_id)
    if b.status != "draft":
        raise ConflictError(f"Batch is {b.status}")
    if not b.payments:
        raise ValidationFailedError("Batch has no payments")
    b.submitted_at = datetime.now(UTC)
    return _transition(db, actor, b, "submit", "awaiting_approval")


def approve(db: Session, actor: User, batch_id: uuid.UUID) -> PaymentBatch:
    b = get_batch(db, actor, batch_id)
    if b.status != "awaiting_approval":
        raise ConflictError(f"Batch is {b.status}")
    if b.prepared_by == actor.id:
        raise PermissionDeniedError("The person who prepared a payment batch cannot approve it")
    b.approved_by, b.approved_at = actor.id, datetime.now(UTC)
    return _transition(db, actor, b, "approve", "approved")


def cancel(db: Session, actor: User, batch_id: uuid.UUID, reason: str) -> PaymentBatch:
    b = get_batch(db, actor, batch_id)
    if b.status not in ("draft", "awaiting_approval", "approved"):
        raise ConflictError("Only a batch that has not been exported can be cancelled")
    for p in b.payments:
        p.status, p.failure_reason = "failed", f"Batch cancelled: {reason}"  # frees the payouts for another batch
    return _transition(db, actor, b, "cancel", "cancelled", reason=reason)


def export(db: Session, actor: User, batch_id: uuid.UUID, fmt: str) -> tuple[bytes, str, str]:
    b = get_batch(db, actor, batch_id)
    if b.status not in ("approved", "exported", "partially_completed"):
        raise ConflictError("A batch must be approved before it can be exported")
    pending = [p for p in b.payments if p.status in ("pending", "exported")]
    if not pending:
        raise ValidationFailedError("No payments awaiting processing in this batch")
    exporter = get_exporter(b.method, fmt)
    org = db.get(Organization, b.organization_id)
    data = exporter.render(b.batch_no, org.currency, [
        PaymentInstruction(str(p.id), p.farmer.full_name, p.farmer.membership_no, p.destination or "", p.destination_bank,
                           p.amount, f"{b.batch_no} {p.farmer.membership_no}") for p in pending])
    for p in pending:
        p.status = "exported"  # NOT paid — only results reconciliation can mark paid
    b.export_count += 1
    b.exported_at = datetime.now(UTC)
    if b.status == "approved":
        b.status = "exported"
    audit_service.record(db, action="payment_batch.export", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="payment_batch", entity_id=b.id,
                         after={"format": fmt, "payments": len(pending), "export_no": b.export_count})
    db.commit()
    return data, f"{b.batch_no}.{exporter.file_extension}", exporter.media_type


def _refresh_status(b: PaymentBatch) -> None:
    statuses = {p.status for p in b.payments}
    if statuses <= {"paid", "reversed"} and "paid" in statuses:
        b.status = "paid"
    elif statuses == {"failed"}:
        b.status = "failed"
    elif "paid" in statuses or "failed" in statuses:
        b.status = "partially_completed"


def record_results(db: Session, actor: User, batch_id: uuid.UUID, results: list[dict]) -> PaymentBatch:
    """Record the outcome reported by the bank / mobile-money provider for each payment."""
    b = get_batch(db, actor, batch_id)
    if b.status not in ("exported", "partially_completed"):
        raise ConflictError("Results can only be recorded for an exported batch")
    by_id = {p.id: p for p in b.payments}
    now = datetime.now(UTC)
    for r in results:
        p = by_id.get(r["payment_id"])
        if p is None:
            raise ValidationFailedError(f"Payment {r['payment_id']} is not in this batch")
        if p.status != "exported":
            raise ConflictError(f"Payment for {p.farmer.full_name} is already {p.status}")
        if r["status"] == "paid":
            if not r.get("transaction_ref"):
                raise ValidationFailedError(f"A transaction reference is required for {p.farmer.full_name}")
            p.status, p.transaction_ref, p.paid_at = "paid", r["transaction_ref"], r.get("paid_at") or now
            p.payout.status = "paid"
        else:
            if not r.get("failure_reason"):
                raise ValidationFailedError(f"A failure reason is required for {p.farmer.full_name}")
            p.status, p.failure_reason = "failed", r["failure_reason"]
        p.reconciled_by, p.reconciled_at = actor.id, now
    _refresh_status(b)
    audit_service.record(db, action="payment.reconcile", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="payment_batch", entity_id=b.id,
                         after={"results": [{"payment_id": str(r["payment_id"]), "status": r["status"],
                                             "ref": r.get("transaction_ref")} for r in results]})
    db.commit()
    return get_batch(db, actor, b.id)


def reverse_payment(db: Session, actor: User, batch_id: uuid.UUID, payment_id: uuid.UUID, reason: str) -> PaymentBatch:
    """E.g. money sent to a wrong number and recovered. The payout becomes payable again."""
    b = get_batch(db, actor, batch_id)
    p = next((x for x in b.payments if x.id == payment_id), None)
    if p is None:
        raise NotFoundError("Payment not found")
    if p.status != "paid":
        raise ConflictError("Only a paid payment can be reversed")
    p.status, p.failure_reason = "reversed", f"Reversed: {reason}"
    p.payout.status = "approved"
    _refresh_status(b)
    audit_service.record(db, action="payment.reverse", user_id=actor.id, organization_id=b.organization_id,
                         entity_type="payment", entity_id=p.id, reason=reason,
                         before={"status": "paid", "transaction_ref": p.transaction_ref, "amount": str(p.amount)})
    db.commit()
    return get_batch(db, actor, b.id)

