"""Reports: each report is a function returning (columns, rows, totals) from real records.

One registry, three outputs. The same rows feed the on-screen preview, CSV, Excel and
PDF, so an exported file can never disagree with what the user saw.
"""
import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.orm import Session

from backend.app.database.core.exceptions import NotFoundError, PermissionDeniedError
from app.models import (
    AggregationBatch, Auction, AuctionLot, CollectionCentre, Crop, DeductionType, Delivery, Discrepancy, DispatchBatch,
    Farmer, FarmerPayout, InputLoan, Organization, Payment, PaymentBatch, PayoutLine, PayoutRun, Season, User, Warehouse,
    WarehouseDispatch, WarehouseReceipt, WarehouseReceiptLine,
)
from app.services.scope import org_id, restricted_centre_ids


@dataclass
class Filters:
    date_from: date | None = None
    date_to: date | None = None      # inclusive
    crop_id: uuid.UUID | None = None
    centre_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    farmer_id: uuid.UUID | None = None


@dataclass
class Column:
    key: str
    label: str
    kind: str = "text"   # text | kg | money | int | date | datetime | price


@dataclass
class Report:
    code: str
    title: str
    columns: list[Column]
    rows: list[dict]
    totals: dict = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    filters_text: str = ""


@dataclass(frozen=True)
class ReportDef:
    code: str
    title: str
    category: str            # operational | financial
    permission: str
    fn: Callable
    filters: tuple[str, ...]


def _range(db: Session, org: uuid.UUID, f: Filters):
    """Date filters are calendar days in the AMCOS timezone -> UTC instants."""
    tz = ZoneInfo(db.get(Organization, org).timezone)
    start = datetime.combine(f.date_from, time.min, tz) if f.date_from else None
    end = datetime.combine(f.date_to + timedelta(days=1), time.min, tz) if f.date_to else None
    return start, end


def _delivery_where(db, actor, f: Filters):
    org = org_id(actor)
    start, end = _range(db, org, f)
    c = [Delivery.organization_id == org, Delivery.status == "recorded"]
    if start:
        c.append(Delivery.captured_at >= start)
    if end:
        c.append(Delivery.captured_at < end)
    for col, v in ((Delivery.crop_id, f.crop_id), (Delivery.centre_id, f.centre_id), (Delivery.season_id, f.season_id),
                   (Delivery.farmer_id, f.farmer_id)):
        if v:
            c.append(col == v)
    allowed = restricted_centre_ids(actor)
    if allowed is not None:
        c.append(Delivery.centre_id.in_(allowed))
    return and_(*c)


def _sum(rows, *keys):
    return {k: sum((r[k] or Decimal("0") for r in rows), Decimal("0")) for k in keys}


# ----------------------------------------------------------- operational
def rpt_farmers(db, actor, f):
    org = org_id(actor)
    stmt = (select(Farmer.membership_no, Farmer.full_name, Farmer.phone, Farmer.gender, Farmer.village, Farmer.ward,
                   CollectionCentre.name, Farmer.registration_date, Farmer.status)
            .outerjoin(CollectionCentre, CollectionCentre.id == Farmer.home_centre_id).where(Farmer.organization_id == org))
    if f.centre_id:
        stmt = stmt.where(Farmer.home_centre_id == f.centre_id)
    if f.date_from:
        stmt = stmt.where(Farmer.registration_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(Farmer.registration_date <= f.date_to)
    rows = [dict(zip(("member", "name", "phone", "gender", "village", "ward", "centre", "registered", "status"), r))
            for r in db.execute(stmt.order_by(Farmer.full_name))]
    return [Column("member", "Member no."), Column("name", "Farmer"), Column("phone", "Phone"), Column("gender", "Gender"),
            Column("village", "Village"), Column("ward", "Ward"), Column("centre", "Home centre"),
            Column("registered", "Registered", "date"), Column("status", "Status")], rows, {"count": len(rows)}


def rpt_intake(db, actor, f):
    stmt = (select(Delivery.receipt_no, Delivery.captured_at, Farmer.membership_no, Farmer.full_name, Crop.name,
                   CollectionCentre.name, Delivery.gross_weight, Delivery.tare_weight, Delivery.net_weight, User.full_name,
                   Delivery.source)
            .join(Farmer, Farmer.id == Delivery.farmer_id).join(Crop, Crop.id == Delivery.crop_id)
            .join(CollectionCentre, CollectionCentre.id == Delivery.centre_id).join(User, User.id == Delivery.recorded_by)
            .where(_delivery_where(db, actor, f)).order_by(Delivery.captured_at))
    keys = ("receipt", "captured", "member", "farmer", "crop", "centre", "gross", "tare", "net", "clerk", "source")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt)]
    return [Column("receipt", "Receipt"), Column("captured", "Date & time", "datetime"), Column("member", "Member no."),
            Column("farmer", "Farmer"), Column("crop", "Crop"), Column("centre", "Centre"), Column("gross", "Gross kg", "kg"),
            Column("tare", "Tare kg", "kg"), Column("net", "Net kg", "kg"), Column("clerk", "Clerk"), Column("source", "Source")], \
        rows, {"count": len(rows), **_sum(rows, "gross", "tare", "net")}


def rpt_daily(db, actor, f):
    tz = db.get(Organization, org_id(actor)).timezone
    day = cast(func.timezone(tz, Delivery.captured_at), Date)
    stmt = (select(day, CollectionCentre.name, Crop.name, func.count(), func.count(func.distinct(Delivery.farmer_id)),
                   func.sum(Delivery.net_weight))
            .join(CollectionCentre, CollectionCentre.id == Delivery.centre_id).join(Crop, Crop.id == Delivery.crop_id)
            .where(_delivery_where(db, actor, f)).group_by(day, CollectionCentre.name, Crop.name).order_by(day, CollectionCentre.name))
    rows = [dict(zip(("day", "centre", "crop", "deliveries", "farmers", "net"), r)) for r in db.execute(stmt)]
    return [Column("day", "Date", "date"), Column("centre", "Centre"), Column("crop", "Crop"), Column("deliveries", "Deliveries", "int"),
            Column("farmers", "Farmers", "int"), Column("net", "Net kg", "kg")], rows, _sum(rows, "deliveries", "net")


def _grouped(db, actor, f, label_col, label):
    stmt = (select(label_col, func.count(), func.count(func.distinct(Delivery.farmer_id)), func.sum(Delivery.net_weight),
                   func.avg(Delivery.net_weight))
            .select_from(Delivery).join(Crop, Crop.id == Delivery.crop_id)
            .join(CollectionCentre, CollectionCentre.id == Delivery.centre_id).join(Season, Season.id == Delivery.season_id)
            .where(_delivery_where(db, actor, f)).group_by(label_col).order_by(func.sum(Delivery.net_weight).desc()))
    rows = [{"group": g, "deliveries": n, "farmers": fm, "net": kg, "avg": Decimal(a).quantize(Decimal("0.001"))}
            for g, n, fm, kg, a in db.execute(stmt)]
    return [Column("group", label), Column("deliveries", "Deliveries", "int"), Column("farmers", "Farmers", "int"),
            Column("net", "Net kg", "kg"), Column("avg", "Avg kg / delivery", "kg")], rows, _sum(rows, "deliveries", "net")


def rpt_by_crop(db, actor, f):
    return _grouped(db, actor, f, Crop.name, "Crop")


def rpt_by_centre(db, actor, f):
    return _grouped(db, actor, f, CollectionCentre.name, "Collection centre")


def rpt_by_season(db, actor, f):
    return _grouped(db, actor, f, Season.name, "Season")


def rpt_dispatches(db, actor, f):
    org = org_id(actor)
    stmt = (select(WarehouseDispatch.dispatch_no, WarehouseDispatch.dispatch_date, Warehouse.name, AggregationBatch.batch_no,
                   Crop.name, AggregationBatch.total_net_weight, DispatchBatch.dispatched_weight, WarehouseDispatch.vehicle_reg,
                   WarehouseDispatch.status)
            .join(Warehouse, Warehouse.id == WarehouseDispatch.warehouse_id).join(DispatchBatch)
            .join(AggregationBatch, AggregationBatch.id == DispatchBatch.batch_id).join(Crop, Crop.id == AggregationBatch.crop_id)
            .where(WarehouseDispatch.organization_id == org))
    if f.date_from:
        stmt = stmt.where(WarehouseDispatch.dispatch_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(WarehouseDispatch.dispatch_date <= f.date_to)
    if f.crop_id:
        stmt = stmt.where(AggregationBatch.crop_id == f.crop_id)
    if f.centre_id:
        stmt = stmt.where(AggregationBatch.centre_id == f.centre_id)
    keys = ("dispatch", "date", "warehouse", "batch", "crop", "batch_kg", "dispatched_kg", "vehicle", "status")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt.order_by(WarehouseDispatch.dispatch_date))]
    return [Column("dispatch", "Dispatch"), Column("date", "Date", "date"), Column("warehouse", "Warehouse"), Column("batch", "Batch"),
            Column("crop", "Crop"), Column("batch_kg", "Batch kg", "kg"), Column("dispatched_kg", "Dispatched kg", "kg"),
            Column("vehicle", "Vehicle"), Column("status", "Status")], rows, _sum(rows, "batch_kg", "dispatched_kg")


def rpt_receipts(db, actor, f):
    org = org_id(actor)
    stmt = (select(WarehouseReceipt.receipt_no, WarehouseReceipt.receipt_date, Warehouse.name, AggregationBatch.batch_no,
                   Crop.name, DispatchBatch.dispatched_weight, WarehouseReceiptLine.received_weight,
                   WarehouseReceiptLine.rejected_weight, WarehouseReceiptLine.damaged_weight, WarehouseReceiptLine.accepted_weight)
            .join(Warehouse, Warehouse.id == WarehouseReceipt.warehouse_id).join(WarehouseReceiptLine)
            .join(AggregationBatch, AggregationBatch.id == WarehouseReceiptLine.batch_id).join(Crop, Crop.id == AggregationBatch.crop_id)
            .join(DispatchBatch, DispatchBatch.batch_id == AggregationBatch.id).where(WarehouseReceipt.organization_id == org))
    if f.date_from:
        stmt = stmt.where(WarehouseReceipt.receipt_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(WarehouseReceipt.receipt_date <= f.date_to)
    if f.crop_id:
        stmt = stmt.where(AggregationBatch.crop_id == f.crop_id)
    keys = ("receipt", "date", "warehouse", "batch", "crop", "dispatched", "received", "rejected", "damaged", "accepted")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt.order_by(WarehouseReceipt.receipt_date))]
    for r in rows:
        r["difference"] = r["received"] - r["dispatched"]
    return [Column("receipt", "Warehouse receipt"), Column("date", "Date", "date"), Column("warehouse", "Warehouse"),
            Column("batch", "Batch"), Column("crop", "Crop"), Column("dispatched", "Dispatched kg", "kg"),
            Column("received", "Received kg", "kg"), Column("difference", "Difference kg", "kg"), Column("rejected", "Rejected kg", "kg"),
            Column("damaged", "Damaged kg", "kg"), Column("accepted", "Accepted kg", "kg")], \
        rows, _sum(rows, "dispatched", "received", "difference", "rejected", "damaged", "accepted")


def rpt_discrepancies(db, actor, f):
    org = org_id(actor)
    stmt = (select(AggregationBatch.batch_no, Discrepancy.stage, Discrepancy.expected_weight, Discrepancy.actual_weight,
                   Discrepancy.difference, Discrepancy.status, Discrepancy.explanation, Discrepancy.created_at)
            .join(AggregationBatch, AggregationBatch.id == Discrepancy.batch_id).where(Discrepancy.organization_id == org))
    if f.crop_id:
        stmt = stmt.where(AggregationBatch.crop_id == f.crop_id)
    keys = ("batch", "stage", "expected", "actual", "difference", "status", "explanation", "flagged")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt.order_by(Discrepancy.created_at))]
    for r in rows:
        r["pct"] = (r["difference"] * 100 / r["expected"]).quantize(Decimal("0.01")) if r["expected"] else None
    return [Column("batch", "Batch"), Column("stage", "Stage"), Column("expected", "Expected kg", "kg"),
            Column("actual", "Actual kg", "kg"), Column("difference", "Difference kg", "kg"), Column("pct", "Diff %"),
            Column("status", "Status"), Column("explanation", "Explanation"), Column("flagged", "Flagged", "datetime")], \
        rows, _sum(rows, "difference")


# ----------------------------------------------------------- financial
def rpt_auction_sales(db, actor, f):
    org = org_id(actor)
    stmt = (select(Auction.auction_ref, Auction.auction_date, Crop.name, AuctionLot.lot_no, AggregationBatch.batch_no,
                   AuctionLot.quantity_sold, AuctionLot.price_per_kg, AuctionLot.total_value, AuctionLot.buyer, Auction.status)
            .select_from(Auction).join(AuctionLot, AuctionLot.auction_id == Auction.id).join(Crop, Crop.id == Auction.crop_id)
            .join(AggregationBatch, AggregationBatch.id == AuctionLot.batch_id)
            .where(Auction.organization_id == org))
    if f.date_from:
        stmt = stmt.where(Auction.auction_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(Auction.auction_date <= f.date_to)
    if f.crop_id:
        stmt = stmt.where(Auction.crop_id == f.crop_id)
    if f.season_id:
        stmt = stmt.where(Auction.season_id == f.season_id)
    keys = ("auction", "date", "crop", "lot", "batch", "kg", "price", "value", "buyer", "status")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt.order_by(Auction.auction_date, AuctionLot.lot_no))]
    t = _sum(rows, "kg", "value")
    t["price"] = (t["value"] / t["kg"]).quantize(Decimal("0.0001")) if t["kg"] else None
    return [Column("auction", "Auction"), Column("date", "Date", "date"), Column("crop", "Crop"), Column("lot", "Lot"),
            Column("batch", "Batch"), Column("kg", "Sold kg", "kg"), Column("price", "Price/kg", "price"),
            Column("value", "Value", "money"), Column("buyer", "Buyer"), Column("status", "Status")], rows, t


def _payout_stmt(actor, f, *cols):
    org = org_id(actor)
    stmt = (select(*cols).select_from(FarmerPayout).join(PayoutRun).join(Farmer, Farmer.id == FarmerPayout.farmer_id)
            .where(PayoutRun.organization_id == org, PayoutRun.status == "approved"))
    if f.crop_id:
        stmt = stmt.where(PayoutRun.crop_id == f.crop_id)
    if f.season_id:
        stmt = stmt.where(PayoutRun.season_id == f.season_id)
    if f.farmer_id:
        stmt = stmt.where(FarmerPayout.farmer_id == f.farmer_id)
    if f.centre_id:
        stmt = stmt.where(Farmer.home_centre_id == f.centre_id)
    return stmt


def _paid_subq():
    return (select(Payment.farmer_payout_id, func.sum(Payment.amount).label("paid"))
            .where(Payment.status == "paid").group_by(Payment.farmer_payout_id).subquery())


def rpt_earnings(db, actor, f):
    paid = _paid_subq()
    stmt = _payout_stmt(actor, f, PayoutRun.run_no, Farmer.membership_no, Farmer.full_name, FarmerPayout.eligible_weight,
                        FarmerPayout.gross_amount, FarmerPayout.total_deductions, FarmerPayout.net_payable,
                        func.coalesce(paid.c.paid, 0), FarmerPayout.status) \
        .outerjoin(paid, paid.c.farmer_payout_id == FarmerPayout.id).order_by(Farmer.full_name)
    keys = ("run", "member", "farmer", "kg", "gross", "deductions", "net", "paid", "status")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt)]
    for r in rows:
        r["unpaid"] = r["net"] - r["paid"] if r["status"] != "needs_review" else Decimal("0")
    return [Column("run", "Payout run"), Column("member", "Member no."), Column("farmer", "Farmer"), Column("kg", "Paid kg", "kg"),
            Column("gross", "Gross", "money"), Column("deductions", "Deductions", "money"), Column("net", "Net payable", "money"),
            Column("paid", "Paid", "money"), Column("unpaid", "Unpaid", "money"), Column("status", "Status")], \
        rows, _sum(rows, "kg", "gross", "deductions", "net", "paid", "unpaid")


def rpt_outstanding(db, actor, f):
    cols, rows, _ = rpt_earnings(db, actor, f)
    rows = [r for r in rows if r["unpaid"] > 0 or r["status"] == "needs_review"]
    return cols, rows, _sum(rows, "kg", "gross", "deductions", "net", "paid", "unpaid")


def rpt_levies(db, actor, f):
    stmt = _payout_stmt(actor, f, func.coalesce(DeductionType.name, "Input loan repayments"), PayoutLine.line_type,
                        func.count(func.distinct(FarmerPayout.farmer_id)), func.sum(PayoutLine.amount)) \
        .join(PayoutLine, PayoutLine.farmer_payout_id == FarmerPayout.id) \
        .outerjoin(DeductionType, DeductionType.id == PayoutLine.deduction_type_id) \
        .where(PayoutLine.line_type != "earning").group_by(DeductionType.name, PayoutLine.line_type)
    rows = [dict(zip(("name", "type", "farmers", "amount"), r)) for r in db.execute(stmt)]
    return [Column("name", "Deduction"), Column("type", "Type"), Column("farmers", "Farmers", "int"),
            Column("amount", "Amount collected", "money")], rows, _sum(rows, "amount")


def rpt_loans(db, actor, f):
    org = org_id(actor)
    stmt = select(InputLoan).join(Farmer).where(InputLoan.organization_id == org)
    if f.farmer_id:
        stmt = stmt.where(InputLoan.farmer_id == f.farmer_id)
    if f.centre_id:
        stmt = stmt.where(Farmer.home_centre_id == f.centre_id)
    from sqlalchemy.orm import selectinload
    loans = db.scalars(stmt.options(selectinload(InputLoan.farmer), selectinload(InputLoan.repayments))
                       .order_by(InputLoan.issue_date)).all()
    rows = [{"loan": l.loan_ref, "issued": l.issue_date, "member": l.farmer.membership_no, "farmer": l.farmer.full_name,
             "inputs": l.description, "principal": l.principal, "repaid": l.repaid, "outstanding": l.outstanding,
             "status": l.status} for l in loans]
    return [Column("loan", "Loan"), Column("issued", "Issued", "date"), Column("member", "Member no."), Column("farmer", "Farmer"),
            Column("inputs", "Inputs"), Column("principal", "Principal", "money"), Column("repaid", "Repaid", "money"),
            Column("outstanding", "Outstanding", "money"), Column("status", "Status")], rows, _sum(rows, "principal", "repaid", "outstanding")


def _payments(db, actor, f, statuses: tuple[str, ...] | None):
    org = org_id(actor)
    stmt = (select(PaymentBatch.batch_no, PaymentBatch.method, Farmer.membership_no, Farmer.full_name, Payment.destination,
                   Payment.amount, Payment.status, Payment.transaction_ref, Payment.paid_at, Payment.failure_reason)
            .join(PaymentBatch).join(Farmer, Farmer.id == Payment.farmer_id).where(PaymentBatch.organization_id == org))
    if statuses:
        stmt = stmt.where(Payment.status.in_(statuses))
    if f.farmer_id:
        stmt = stmt.where(Payment.farmer_id == f.farmer_id)
    start, end = _range(db, org, f)
    if start:
        stmt = stmt.where(Payment.created_at >= start)
    if end:
        stmt = stmt.where(Payment.created_at < end)
    keys = ("batch", "method", "member", "farmer", "destination", "amount", "status", "reference", "paid_at", "reason")
    rows = [dict(zip(keys, r)) for r in db.execute(stmt.order_by(PaymentBatch.batch_no, Farmer.full_name))]
    return [Column("batch", "Batch"), Column("method", "Method"), Column("member", "Member no."), Column("farmer", "Farmer"),
            Column("destination", "Destination"), Column("amount", "Amount", "money"), Column("status", "Status"),
            Column("reference", "Transaction ref."), Column("paid_at", "Paid at", "datetime"), Column("reason", "Failure / note")], \
        rows, {"count": len(rows), **_sum(rows, "amount")}


def rpt_payments_completed(db, actor, f):
    return _payments(db, actor, f, ("paid",))


def rpt_payments_failed(db, actor, f):
    return _payments(db, actor, f, ("failed", "reversed"))


def rpt_reconciliation(db, actor, f):
    org = org_id(actor)
    stmt = (select(PaymentBatch.batch_no, PaymentBatch.method, PaymentBatch.status, Payment.status, func.count(), func.sum(Payment.amount))
            .join(Payment).where(PaymentBatch.organization_id == org)
            .group_by(PaymentBatch.batch_no, PaymentBatch.method, PaymentBatch.status, Payment.status).order_by(PaymentBatch.batch_no))
    agg: dict[str, dict] = {}
    for bno, method, bstatus, pstatus, n, amount in db.execute(stmt):
        row = agg.setdefault(bno, {"batch": bno, "method": method, "status": bstatus, "payments": 0, "total": Decimal("0"),
                                   "paid": Decimal("0"), "failed": Decimal("0"), "awaiting": Decimal("0")})
        row["payments"] += n
        row["total"] += amount
        key = {"paid": "paid", "failed": "failed", "reversed": "failed"}.get(pstatus, "awaiting")
        row[key] += amount
    rows = list(agg.values())
    return [Column("batch", "Batch"), Column("method", "Method"), Column("status", "Batch status"), Column("payments", "Payments", "int"),
            Column("total", "Total", "money"), Column("paid", "Confirmed paid", "money"), Column("failed", "Failed / reversed", "money"),
            Column("awaiting", "Awaiting result", "money")], rows, _sum(rows, "payments", "total", "paid", "failed", "awaiting")


REPORTS: dict[str, ReportDef] = {d.code: d for d in [
    ReportDef("farmers", "Farmer registration", "operational", "report.operational", rpt_farmers, ("date", "centre")),
    ReportDef("intake", "Produce intake (all deliveries)", "operational", "report.operational", rpt_intake, ("date", "crop", "centre", "season", "farmer")),
    ReportDef("daily", "Daily collection", "operational", "report.operational", rpt_daily, ("date", "crop", "centre", "season")),
    ReportDef("by_crop", "Collection by crop", "operational", "report.operational", rpt_by_crop, ("date", "centre", "season")),
    ReportDef("by_centre", "Collection centre performance", "operational", "report.operational", rpt_by_centre, ("date", "crop", "season")),
    ReportDef("by_season", "Seasonal produce", "operational", "report.operational", rpt_by_season, ("crop", "centre")),
    ReportDef("dispatches", "Warehouse dispatches", "operational", "report.operational", rpt_dispatches, ("date", "crop", "centre")),
    ReportDef("receipts", "Warehouse receipts", "operational", "report.operational", rpt_receipts, ("date", "crop")),
    ReportDef("discrepancies", "Warehouse discrepancies", "operational", "report.operational", rpt_discrepancies, ("crop",)),
    ReportDef("auction_sales", "Auction sales", "financial", "report.financial", rpt_auction_sales, ("date", "crop", "season")),
    ReportDef("earnings", "Farmer earnings & net payments", "financial", "report.financial", rpt_earnings, ("crop", "season", "centre", "farmer")),
    ReportDef("outstanding", "Outstanding payments", "financial", "report.financial", rpt_outstanding, ("crop", "season", "centre", "farmer")),
    ReportDef("levies", "Levy & deduction collection", "financial", "report.financial", rpt_levies, ("crop", "season", "centre")),
    ReportDef("loans", "Input loans", "financial", "report.financial", rpt_loans, ("centre", "farmer")),
    ReportDef("payments_completed", "Completed payments", "financial", "report.financial", rpt_payments_completed, ("date", "farmer")),
    ReportDef("payments_failed", "Failed & reversed payments", "financial", "report.financial", rpt_payments_failed, ("date", "farmer")),
    ReportDef("reconciliation", "Payment reconciliation", "financial", "report.financial", rpt_reconciliation, ()),
]}


def catalogue(actor: User) -> list[dict]:
    return [{"code": d.code, "title": d.title, "category": d.category, "filters": list(d.filters)}
            for d in REPORTS.values() if d.permission in actor.permission_codes]


def run(db: Session, actor: User, code: str, f: Filters) -> Report:
    d = REPORTS.get(code)
    if d is None:
        raise NotFoundError("Unknown report")
    if d.permission not in actor.permission_codes:
        raise PermissionDeniedError(f"Missing permission: {d.permission}")
    cols, rows, totals = d.fn(db, actor, f)
    parts = []
    if f.date_from or f.date_to:
        parts.append(f"{f.date_from or '…'} to {f.date_to or '…'}")
    for model, val in ((Crop, f.crop_id), (CollectionCentre, f.centre_id), (Season, f.season_id), (Farmer, f.farmer_id)):
        if val and (obj := db.get(model, val)):
            parts.append(getattr(obj, "name", None) or obj.full_name)
    return Report(code=code, title=d.title, columns=cols, rows=rows, totals=totals, filters_text=" · ".join(parts) or "All records")


# ----------------------------------------------------------- renderers
def _fmt(v, kind: str, tz: ZoneInfo) -> str:
    if v is None:
        return ""
    if kind == "money":
        return f"{v:,.2f}"
    if kind in ("kg",):
        return f"{v:,.3f}"
    if kind == "price":
        return f"{v:,.4f}"
    if kind == "datetime" and isinstance(v, datetime):
        return v.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def to_csv(r: Report, tz: ZoneInfo) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([r.title])
    w.writerow([f"Filters: {r.filters_text}", f"Generated: {r.generated_at.astimezone(tz):%Y-%m-%d %H:%M}"])
    w.writerow([c.label for c in r.columns])
    for row in r.rows:
        # raw values (no thousands separators) so spreadsheets can calculate with them
        w.writerow([("" if row.get(c.key) is None else row[c.key].astimezone(tz).strftime("%Y-%m-%d %H:%M")
                     if c.kind == "datetime" and isinstance(row.get(c.key), datetime) else row.get(c.key)) for c in r.columns])
    w.writerow(["TOTAL"] + [r.totals.get(c.key, "") for c in r.columns[1:]])
    return buf.getvalue().encode("utf-8-sig")


def to_xlsx(r: Report, tz: ZoneInfo) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = r.code[:31]
    ws.append([r.title])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Filters: {r.filters_text}"])
    ws.append([f"Generated: {r.generated_at.astimezone(tz):%Y-%m-%d %H:%M}"])
    ws.append([])
    ws.append([c.label for c in r.columns])
    for cell in ws[5]:
        cell.font = Font(bold=True)
    fmt = {"money": "#,##0.00", "kg": "#,##0.000", "price": "#,##0.0000", "int": "#,##0"}
    for row in r.rows:
        vals = []
        for c in r.columns:
            v = row.get(c.key)
            if isinstance(v, Decimal):
                v = float(v)
            elif isinstance(v, datetime):
                v = v.astimezone(tz).replace(tzinfo=None)
            vals.append(v)
        ws.append(vals)
        for i, c in enumerate(r.columns, start=1):
            if c.kind in fmt:
                ws.cell(row=ws.max_row, column=i).number_format = fmt[c.kind]
    ws.append(["TOTAL"] + [float(r.totals[c.key]) if isinstance(r.totals.get(c.key), Decimal) else r.totals.get(c.key)
                           for c in r.columns[1:]])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for i, c in enumerate(r.columns, start=1):
        ws.column_dimensions[ws.cell(row=5, column=i).column_letter].width = max(12, min(40, len(c.label) + 6))
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_pdf(r: Report, org: Organization) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    tz = ZoneInfo(org.timezone)
    buf = io.BytesIO()
    page = landscape(A4) if len(r.columns) > 6 else A4
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=r.title)
    styles = getSampleStyleSheet()
    cell = styles["BodyText"].clone("cell", fontSize=7, leading=8.5)
    story = [Paragraph(f"<b>{org.name}</b>", styles["Title"]), Paragraph(r.title, styles["Heading2"]),
             Paragraph(f"Filters: {r.filters_text} &nbsp;&nbsp; Generated: {r.generated_at.astimezone(tz):%d %b %Y %H:%M}", cell)]
    if org.is_demo:
        story.append(Paragraph("<font color='red'>DEMONSTRATION DATA</font>", cell))
    story.append(Spacer(1, 4 * mm))
    right = {"money", "kg", "price", "int"}
    data = [[Paragraph(f"<b>{c.label}</b>", cell) for c in r.columns]]
    # numbers as plain strings so the column ALIGN RIGHT applies; text wraps via Paragraph
    def c_(v, c):
        txt = _fmt(v, c.kind, tz)
        return txt if c.kind in right else Paragraph(txt.replace("&", "&amp;").replace("<", "&lt;"), cell)
    data += [[c_(row.get(c.key), c) for c in r.columns] for row in r.rows]
    data.append(["TOTAL"] + [_fmt(r.totals.get(c.key), c.kind, tz) for c in r.columns[1:]])
    t = Table(data, repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
             ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("FONTSIZE", (0, 1), (-1, -1), 7), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
    for i, c in enumerate(r.columns):
        if c.kind in right:
            style.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"{len(r.rows)} rows. Figures are generated from system records at the time shown.", cell))
    doc.build(story)
    return buf.getvalue()
