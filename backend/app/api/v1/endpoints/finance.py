import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import User
from app.schemas.finance import (
    DeductionCreate, DeductionRead, DeductionUpdate, EligiblePayout, LoanCreate, LoanRead, PaymentBatchCreate,
    PaymentBatchRead, ReasonBody, RepaymentCreate, ResultsBody, RunCreate, RunRead, RunSummary, Statement,
)
from app.services import finance_service as fin
from app.services import payment_service as pay
from app.services.notification_service import process_queue_background

router = APIRouter()
db_dep = Depends(get_db)


# ---- Deductions
@router.get("/deductions", response_model=list[DeductionRead], tags=["deductions"])
def list_deductions(u: User = Depends(require_permission("payout.view")), db: Session = db_dep):
    return fin.list_deductions(db, u)


@router.post("/deductions", response_model=DeductionRead, status_code=201, tags=["deductions"])
def create_deduction(body: DeductionCreate, u: User = Depends(require_permission("deduction.manage")), db: Session = db_dep):
    return fin.create_deduction(db, u, body.model_dump())


@router.patch("/deductions/{dt_id}", response_model=DeductionRead, tags=["deductions"])
def update_deduction(dt_id: uuid.UUID, body: DeductionUpdate, u: User = Depends(require_permission("deduction.manage")),
                     db: Session = db_dep):
    return fin.update_deduction(db, u, dt_id, body.model_dump(exclude_unset=True))


# ---- Loans
@router.get("/loans", response_model=list[LoanRead], tags=["loans"])
def list_loans(farmer_id: uuid.UUID | None = None, status: str | None = Query(None, pattern="^(active|repaid|written_off)$"),
               u: User = Depends(require_permission("farmer.view_financial")), db: Session = db_dep):
    return fin.list_loans(db, u, farmer_id, status)


@router.post("/loans", response_model=LoanRead, status_code=201, tags=["loans"])
def create_loan(body: LoanCreate, u: User = Depends(require_permission("loan.manage")), db: Session = db_dep):
    return fin.create_loan(db, u, body.model_dump())


@router.get("/loans/{loan_id}", response_model=LoanRead, tags=["loans"])
def get_loan(loan_id: uuid.UUID, u: User = Depends(require_permission("farmer.view_financial")), db: Session = db_dep):
    return fin.get_loan(db, u, loan_id)


@router.post("/loans/{loan_id}/repayments", response_model=LoanRead, status_code=201, tags=["loans"])
def cash_repayment(loan_id: uuid.UUID, body: RepaymentCreate, u: User = Depends(require_permission("loan.manage")),
                   db: Session = db_dep):
    return fin.record_cash_repayment(db, u, loan_id, body.amount, body.repayment_date, body.reference)


# ---- Payout runs
@router.get("/payout-runs", response_model=list[RunSummary], tags=["payouts"])
def list_runs(u: User = Depends(require_permission("payout.view")), db: Session = db_dep):
    return fin.list_runs(db, u)


@router.post("/payout-runs", response_model=RunRead, status_code=201, tags=["payouts"])
def calculate(body: RunCreate, u: User = Depends(require_permission("payout.calculate")), db: Session = db_dep):
    return fin.calculate_run(db, u, body.crop_id, body.season_id, body.loss_policy, body.notes)


@router.get("/payout-runs/{run_id}", response_model=RunRead, tags=["payouts"])
def get_run(run_id: uuid.UUID, u: User = Depends(require_permission("payout.view")), db: Session = db_dep):
    return fin.get_run(db, u, run_id)


@router.post("/payout-runs/{run_id}/approve", response_model=RunRead, tags=["payouts"])
def approve_run(run_id: uuid.UUID, u: User = Depends(require_permission("payout.approve")), db: Session = db_dep):
    return fin.approve_run(db, u, run_id)


@router.post("/payout-runs/{run_id}/cancel", response_model=RunRead, tags=["payouts"])
def cancel_run(run_id: uuid.UUID, body: ReasonBody, u: User = Depends(require_permission("payout.calculate")),
               db: Session = db_dep):
    return fin.cancel_run(db, u, run_id, body.reason)


@router.get("/farmers/{farmer_id}/statement", response_model=Statement, tags=["payouts"])
def statement(farmer_id: uuid.UUID, u: User = Depends(require_permission("farmer.view_financial")), db: Session = db_dep):
    return fin.farmer_statement(db, u, farmer_id)


# ---- Payment batches
@router.get("/payment-batches/eligible", response_model=list[EligiblePayout], tags=["payments"])
def eligible(method: str = Query(pattern="^(mobile_money|bank|cash)$"),
             u: User = Depends(require_permission("payment_batch.prepare")), db: Session = db_dep):
    return [EligiblePayout(payout_id=e["payout"].id, run_no=e["payout"].run.run_no, farmer=e["payout"].farmer,
                           net_payable=e["payout"].net_payable, problem=e["problem"])
            for e in pay.eligible_payouts(db, u, method)]


@router.get("/payment-batches", response_model=list[PaymentBatchRead], tags=["payments"])
def list_payment_batches(status: str | None = None, u: User = Depends(require_permission("payout.view")),
                         db: Session = db_dep):
    return pay.list_batches(db, u, status)


@router.post("/payment-batches", response_model=PaymentBatchRead, status_code=201, tags=["payments"])
def create_payment_batch(body: PaymentBatchCreate, u: User = Depends(require_permission("payment_batch.prepare")),
                         db: Session = db_dep):
    return pay.create_batch(db, u, body.method, body.payout_ids, body.notes)


@router.get("/payment-batches/{batch_id}", response_model=PaymentBatchRead, tags=["payments"])
def get_payment_batch(batch_id: uuid.UUID, u: User = Depends(require_permission("payout.view")), db: Session = db_dep):
    return pay.get_batch(db, u, batch_id)


@router.post("/payment-batches/{batch_id}/submit", response_model=PaymentBatchRead, tags=["payments"])
def submit(batch_id: uuid.UUID, u: User = Depends(require_permission("payment_batch.prepare")), db: Session = db_dep):
    return pay.submit(db, u, batch_id)


@router.post("/payment-batches/{batch_id}/approve", response_model=PaymentBatchRead, tags=["payments"])
def approve(batch_id: uuid.UUID, u: User = Depends(require_permission("payment_batch.approve")), db: Session = db_dep):
    return pay.approve(db, u, batch_id)


@router.post("/payment-batches/{batch_id}/cancel", response_model=PaymentBatchRead, tags=["payments"])
def cancel(batch_id: uuid.UUID, body: ReasonBody, u: User = Depends(require_permission("payment_batch.prepare")),
           db: Session = db_dep):
    return pay.cancel(db, u, batch_id, body.reason)


@router.post("/payment-batches/{batch_id}/export", tags=["payments"])
def export(batch_id: uuid.UUID, format: str = Query("csv", pattern="^(csv|xlsx)$"),
           u: User = Depends(require_permission("payment_batch.prepare")), db: Session = db_dep):
    data, filename, media = pay.export(db, u, batch_id, format)
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/payment-batches/{batch_id}/results", response_model=PaymentBatchRead, tags=["payments"])
def results(batch_id: uuid.UUID, body: ResultsBody, background: BackgroundTasks,
            u: User = Depends(require_permission("payment.reconcile")), db: Session = db_dep):
    out = pay.record_results(db, u, batch_id, [r.model_dump() for r in body.results])
    background.add_task(process_queue_background, u.organization_id)
    return out


@router.post("/payment-batches/{batch_id}/payments/{payment_id}/reverse", response_model=PaymentBatchRead, tags=["payments"])
def reverse(batch_id: uuid.UUID, payment_id: uuid.UUID, body: ReasonBody,
            u: User = Depends(require_permission("payment_batch.approve")), db: Session = db_dep):
    return pay.reverse_payment(db, u, batch_id, payment_id, body.reason)
