"""Deduction types, input loans, payout runs and farmer statements.

Payout run lifecycle:
  calculate -> 'calculated'  (can be cancelled and recalculated freely)
  approve   -> 'approved'    (by a different user; loan repayments are booked; frozen)
  cancel    -> 'cancelled'   (only before approval; releases its lot allocations)
"""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.models import (
    Auction, AuctionLot, Crop, DeductionType, Delivery, FarmerPayout, Farmer, InputLoan, LoanRepayment, LotAllocation,
    Organization, Payment, PayoutLine, PayoutRun, PayoutRunAllocation, Season, User,
)
from app.services import audit_service, payout_engine as engine
from app.services.numbering import next_number
from app.services.scope import org_id


def _today(db: Session, org: uuid.UUID) -> date:
    return datetime.now(ZoneInfo(db.get(Organization, org).timezone)).date()


# ============================================================ deduction types
def list_deductions(db: Session, actor: User) -> list[DeductionType]:
    return list(db.scalars(select(DeductionType).where(DeductionType.organization_id == org_id(actor))
                           .options(selectinload(DeductionType.crop), selectinload(DeductionType.season))
                           .order_by(DeductionType.priority, DeductionType.name)))


def _get_deduction(db: Session, actor: User, dt_id: uuid.UUID) -> DeductionType:
    dt = db.get(DeductionType, dt_id)
    if dt is None or dt.organization_id != org_id(actor):
        raise NotFoundError("Deduction type not found")
    return dt


def _check_scope(db: Session, org: uuid.UUID, crop_id, season_id) -> None:
    for model, ident in ((Crop, crop_id), (Season, season_id)):
        if ident is None:
            continue
        obj = db.get(model, ident)
        if obj is None or obj.organization_id != org:
            raise ValidationFailedError(f"{model.__name__} not found")


def create_deduction(db: Session, actor: User, data: dict) -> DeductionType:
    org = org_id(actor)
    _check_scope(db, org, data.get("crop_id"), data.get("season_id"))
    data["code"] = data["code"].upper()
    dt = DeductionType(organization_id=org, **data)
    db.add(dt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Deduction code {data['code']} already exists") from exc
    audit_service.record(db, action="deduction.create", user_id=actor.id, organization_id=org, entity_type="deduction_type",
                         entity_id=dt.id, after={k: str(v) for k, v in data.items()})
    db.commit()
    return dt


def update_deduction(db: Session, actor: User, dt_id: uuid.UUID, changes: dict) -> DeductionType:
    """Rate changes only affect FUTURE calculations: approved payouts keep the rate they used
    (it is copied into each payout line)."""
    dt = _get_deduction(db, actor, dt_id)
    if "crop_id" in changes or "season_id" in changes:
        _check_scope(db, dt.organization_id, changes.get("crop_id"), changes.get("season_id"))
    before = {k: str(getattr(dt, k)) for k in changes}
    for k, v in changes.items():
        setattr(dt, k, v)
    audit_service.record(db, action="deduction.update", user_id=actor.id, organization_id=dt.organization_id,
                         entity_type="deduction_type", entity_id=dt.id, before=before,
                         after={k: str(v) for k, v in changes.items()})
    db.commit()
    return dt


def applicable_deductions(db: Session, org: uuid.UUID, crop_id, season_id, on: date) -> list[DeductionType]:
    return list(db.scalars(select(DeductionType).where(
        DeductionType.organization_id == org, DeductionType.is_active.is_(True),
        or_(DeductionType.crop_id.is_(None), DeductionType.crop_id == crop_id),
        or_(DeductionType.season_id.is_(None), DeductionType.season_id == season_id),
        DeductionType.effective_from <= on,
        or_(DeductionType.effective_to.is_(None), DeductionType.effective_to >= on))))


# ============================================================ loans
def _loan_options():
    return (selectinload(InputLoan.farmer), selectinload(InputLoan.repayments))


def list_loans(db: Session, actor: User, farmer_id=None, status: str | None = None) -> list[InputLoan]:
    stmt = select(InputLoan).where(InputLoan.organization_id == org_id(actor)).options(*_loan_options())
    if farmer_id:
        stmt = stmt.where(InputLoan.farmer_id == farmer_id)
    if status:
        stmt = stmt.where(InputLoan.status == status)
    return list(db.scalars(stmt.order_by(InputLoan.issue_date.desc())))


def get_loan(db: Session, actor: User, loan_id: uuid.UUID) -> InputLoan:
    loan = db.scalar(select(InputLoan).where(InputLoan.id == loan_id, InputLoan.organization_id == org_id(actor))
                     .options(*_loan_options()))
    if loan is None:
        raise NotFoundError("Loan not found")
    return loan


def create_loan(db: Session, actor: User, data: dict) -> InputLoan:
    org = org_id(actor)
    farmer = db.get(Farmer, data["farmer_id"])
    if farmer is None or farmer.organization_id != org:
        raise ValidationFailedError("Farmer not found")
    if not data.get("loan_ref"):
        code = db.get(Organization, org).code
        data["loan_ref"] = f"{code}-L{_today(db, org).year}-{next_number(db, org, 'loan'):04d}"
    loan = InputLoan(organization_id=org, created_by=actor.id, **data)
    db.add(loan)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"Loan reference {data['loan_ref']} already exists") from exc
    audit_service.record(db, action="loan.create", user_id=actor.id, organization_id=org, entity_type="loan",
                         entity_id=loan.id, after={"loan_ref": loan.loan_ref, "farmer": farmer.membership_no,
                                                   "principal": str(loan.principal)})
    db.commit()
    return get_loan(db, actor, loan.id)


def record_cash_repayment(db: Session, actor: User, loan_id: uuid.UUID, amount: Decimal, repayment_date: date,
                          reference: str | None) -> InputLoan:
    loan = get_loan(db, actor, loan_id)
    if loan.status != "active":
        raise ConflictError(f"Loan is {loan.status}")
    if amount > loan.outstanding:
        raise ValidationFailedError(f"Repayment exceeds the outstanding balance of {loan.outstanding}")
    db.add(LoanRepayment(loan_id=loan.id, amount=amount, source="cash", repayment_date=repayment_date,
                         reference=reference, recorded_by=actor.id))
    db.flush()
    db.refresh(loan)
    if loan.outstanding == 0:
        loan.status = "repaid"
    audit_service.record(db, action="loan.cash_repayment", user_id=actor.id, organization_id=loan.organization_id,
                         entity_type="loan", entity_id=loan.id, after={"amount": str(amount), "reference": reference})
    db.commit()
    return get_loan(db, actor, loan.id)


def _pending_loan_deductions(db: Session, org: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """Loan amounts already reserved by calculated (not yet approved) runs, so two draft runs
    can't both plan to recover the same balance."""
    rows = db.execute(select(PayoutLine.loan_id, PayoutLine.amount)
                      .join(FarmerPayout).join(PayoutRun)
                      .where(PayoutRun.organization_id == org, PayoutRun.status == "calculated",
                             PayoutLine.loan_id.is_not(None))).all()
    out: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for loan_id, amount in rows:
        out[loan_id] += amount
    return out


# ============================================================ payout runs
def _run_options():
    return (selectinload(PayoutRun.crop), selectinload(PayoutRun.season),
            selectinload(PayoutRun.payouts).selectinload(FarmerPayout.farmer),
            selectinload(PayoutRun.payouts).selectinload(FarmerPayout.lines))


def get_run(db: Session, actor: User, run_id: uuid.UUID) -> PayoutRun:
    run = db.scalar(select(PayoutRun).where(PayoutRun.id == run_id, PayoutRun.organization_id == org_id(actor))
                    .options(*_run_options()))
    if run is None:
        raise NotFoundError("Payout run not found")
    return run


def list_runs(db: Session, actor: User) -> list[PayoutRun]:
    return list(db.scalars(select(PayoutRun).where(PayoutRun.organization_id == org_id(actor))
                           .options(selectinload(PayoutRun.crop), selectinload(PayoutRun.season))
                           .order_by(PayoutRun.calculated_at.desc())))


def unpaid_allocations(db: Session, org: uuid.UUID, crop_id, season_id) -> list[LotAllocation]:
    """Allocations from APPROVED auctions not yet included in any live payout run."""
    taken = select(PayoutRunAllocation.allocation_id)
    return list(db.scalars(
        select(LotAllocation).join(AuctionLot).join(Auction)
        .where(Auction.organization_id == org, Auction.status == "approved", Auction.crop_id == crop_id,
               Auction.season_id == season_id, LotAllocation.id.not_in(taken))
        .options(selectinload(LotAllocation.lot).selectinload(AuctionLot.auction),
                 selectinload(LotAllocation.delivery))
        .order_by(LotAllocation.farmer_id, LotAllocation.delivery_id)))


def calculate_run(db: Session, actor: User, crop_id: uuid.UUID, season_id: uuid.UUID, loss_policy: str,
                  notes: str | None) -> PayoutRun:
    org = org_id(actor)
    _check_scope(db, org, crop_id, season_id)
    allocations = unpaid_allocations(db, org, crop_id, season_id)
    if not allocations:
        raise ValidationFailedError("No sold produce awaiting payment for this crop and season "
                                    "(auctions must be approved first)")
    today = _today(db, org)
    deductions = [engine.DeductionInput(d.id, d.name, d.category, d.calc_method, d.rate, d.applies_per, d.priority)
                  for d in applicable_deductions(db, org, crop_id, season_id, today)]
    reserved = _pending_loan_deductions(db, org)

    by_farmer: dict[uuid.UUID, list[LotAllocation]] = defaultdict(list)
    for a in allocations:
        by_farmer[a.farmer_id].append(a)

    run = PayoutRun(organization_id=org, run_no=f"{db.get(Organization, org).code}-P{today.year}-"
                                                f"{next_number(db, org, f'payout:{today.year}'):04d}",
                    crop_id=crop_id, season_id=season_id, loss_policy=loss_policy, calculated_by=actor.id,
                    calculated_at=datetime.now(UTC), notes=notes)
    db.add(run)
    db.flush()
    for a in allocations:
        db.add(PayoutRunAllocation(run_id=run.id, allocation_id=a.id))

    for farmer_id, allocs in by_farmer.items():
        earnings = [engine.EarningInput(
            a.id, a.delivery_id,
            f"Receipt {a.delivery.receipt_no} · {a.lot.auction.auction_ref} lot {a.lot.lot_no}",
            a.weight_shared if loss_policy == "shared" else a.weight_absorbed, a.price_per_kg) for a in allocs]
        loans = [engine.LoanInput(l.id, l.loan_ref, l.outstanding - reserved.get(l.id, Decimal("0")), l.max_deduction_percent)
                 for l in db.scalars(select(InputLoan).where(InputLoan.farmer_id == farmer_id, InputLoan.status == "active")
                                     .options(selectinload(InputLoan.repayments)).order_by(InputLoan.issue_date))]
        r = engine.calculate(earnings, deductions, loans)
        payout = FarmerPayout(run_id=run.id, farmer_id=farmer_id, eligible_weight=r.eligible_kg, gross_amount=r.gross,
                              total_deductions=r.total_deductions, net_payable=r.net, shortfall=r.shortfall,
                              status="needs_review" if r.needs_review else "calculated", flags=r.flags)
        payout.lines = [PayoutLine(sort_order=i, line_type=l.line_type, description=l.description[:300],
                                   quantity=l.quantity, rate=l.rate, amount=l.amount, lot_allocation_id=l.allocation_id,
                                   deduction_type_id=l.deduction_type_id, loan_id=l.loan_id)
                        for i, l in enumerate(r.lines)]
        db.add(payout)
        run.total_gross += r.gross
        run.total_deductions += r.total_deductions
        run.total_net += r.net
    try:
        db.flush()
    except IntegrityError as exc:  # another run grabbed the same allocations concurrently
        db.rollback()
        raise ConflictError("Another payout run was calculated at the same time; please retry") from exc
    audit_service.record(db, action="payout.calculate", user_id=actor.id, organization_id=org, entity_type="payout_run",
                         entity_id=run.id, after={"run_no": run.run_no, "policy": loss_policy, "farmers": len(by_farmer),
                                                  "gross": str(run.total_gross), "net": str(run.total_net)})
    db.commit()
    return get_run(db, actor, run.id)


def approve_run(db: Session, actor: User, run_id: uuid.UUID) -> PayoutRun:
    run = get_run(db, actor, run_id)
    if run.status != "calculated":
        raise ConflictError(f"Run is {run.status}")
    if run.calculated_by == actor.id:
        raise PermissionDeniedError("A payout run must be approved by someone other than the person who calculated it")
    today = _today(db, run.organization_id)
    for p in run.payouts:
        if p.status == "calculated":
            p.status = "approved"
        for line in p.lines:
            if line.line_type == "loan":
                loan = db.get(InputLoan, line.loan_id)
                if line.amount > loan.outstanding:
                    raise ConflictError(f"Loan {loan.loan_ref} balance changed since calculation; cancel and recalculate")
                db.add(LoanRepayment(loan_id=loan.id, amount=line.amount, source="payout", farmer_payout_id=p.id,
                                     repayment_date=today, reference=run.run_no, recorded_by=actor.id))
                db.flush()
                db.refresh(loan)
                if loan.outstanding == 0:
                    loan.status = "repaid"
    run.status, run.approved_by, run.approved_at = "approved", actor.id, datetime.now(UTC)
    audit_service.record(db, action="payout.approve", user_id=actor.id, organization_id=run.organization_id,
                         entity_type="payout_run", entity_id=run.id,
                         after={"run_no": run.run_no, "net": str(run.total_net),
                                "held_for_review": sum(p.status == "needs_review" for p in run.payouts)})
    db.commit()
    return get_run(db, actor, run.id)


def cancel_run(db: Session, actor: User, run_id: uuid.UUID, reason: str) -> PayoutRun:
    run = get_run(db, actor, run_id)
    if run.status != "calculated":
        raise ConflictError("Only an unapproved run can be cancelled")
    for p in run.payouts:
        p.status = "cancelled"
    db.execute(PayoutRunAllocation.__table__.delete().where(PayoutRunAllocation.run_id == run.id))
    run.status, run.cancelled_reason = "cancelled", reason
    audit_service.record(db, action="payout.cancel", user_id=actor.id, organization_id=run.organization_id,
                         entity_type="payout_run", entity_id=run.id, reason=reason, after={"run_no": run.run_no})
    db.commit()
    return get_run(db, actor, run.id)


# ============================================================ statements
def farmer_statement(db: Session, actor: User, farmer_id: uuid.UUID) -> dict:
    """Everything a farmer is owed and was paid, explainable from original records."""
    farmer = db.get(Farmer, farmer_id)
    if farmer is None or farmer.organization_id != org_id(actor):
        raise NotFoundError("Farmer not found")
    deliveries = list(db.scalars(select(Delivery).where(Delivery.farmer_id == farmer.id)
                                 .options(selectinload(Delivery.crop), selectinload(Delivery.centre))
                                 .order_by(Delivery.captured_at)))
    payouts = list(db.scalars(select(FarmerPayout).join(PayoutRun)
                              .where(FarmerPayout.farmer_id == farmer.id, PayoutRun.status == "approved")
                              .options(selectinload(FarmerPayout.lines),
                                       selectinload(FarmerPayout.run).selectinload(PayoutRun.crop),
                                       selectinload(FarmerPayout.run).selectinload(PayoutRun.season))
                              .order_by(PayoutRun.approved_at)))
    payments = list(db.scalars(select(Payment).where(Payment.farmer_id == farmer.id)
                               .options(selectinload(Payment.batch)).order_by(Payment.created_at)))
    loans = list_loans(db, actor, farmer_id=farmer.id)
    paid = sum((p.amount for p in payments if p.status == "paid"), Decimal("0"))
    payable = sum((p.net_payable for p in payouts if p.status in ("approved", "paid")), Decimal("0"))
    sum_type = lambda t: sum((l.amount for p in payouts for l in p.lines if l.line_type == t), Decimal("0"))  # noqa: E731
    return {
        "farmer": farmer, "deliveries": deliveries, "payouts": payouts, "payments": payments, "loans": loans,
        "totals": {
            "delivered_kg": sum((d.net_weight for d in deliveries if d.status == "recorded"), Decimal("0")),
            "eligible_kg": sum((p.eligible_weight for p in payouts), Decimal("0")),
            "gross": sum((p.gross_amount for p in payouts), Decimal("0")),
            "levies": sum_type("levy"), "other_deductions": sum_type("other"), "loan_deductions": sum_type("loan"),
            "net_payable": payable, "paid": paid, "unpaid": payable - paid,
            "held_for_review": sum((p.net_payable for p in payouts if p.status == "needs_review"), Decimal("0")),
            "loans_outstanding": sum((l.outstanding for l in loans if l.status == "active"), Decimal("0")),
        },
    }
