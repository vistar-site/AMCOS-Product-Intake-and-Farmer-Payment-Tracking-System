"""Farmer payout statement as PDF (same data as GET /farmers/{id}/statement)."""
import io
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Organization


def _m(v) -> str:
    return f"{v:,.2f}"


def render_statement(st: dict, org: Organization) -> bytes:
    tz = ZoneInfo(org.timezone)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Statement {st['farmer'].membership_no}")
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("s", fontSize=8, leading=10)
    f, t = st["farmer"], st["totals"]
    grid = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("FONTSIZE", (0, 0), (-1, -1), 8),
                       ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")), ("ALIGN", (-1, 0), (-1, -1), "RIGHT")])
    story = [Paragraph(f"<b>{org.name}</b>", ss["Title"]), Paragraph("Farmer payout statement", ss["Heading2"]),
             Paragraph(f"{f.full_name} · Member {f.membership_no}" + (f" · {f.phone}" if f.phone else ""), ss["BodyText"])]
    if org.is_demo:
        story.append(Paragraph("<font color='red'>DEMONSTRATION DATA — NOT A VALID STATEMENT</font>", small))
    story.append(Spacer(1, 4 * mm))
    summary = [["Summary", "Amount (TZS)"], ["Delivered (kg)", f"{t['delivered_kg']:,.3f}"], ["Paid weight (kg)", f"{t['eligible_kg']:,.3f}"],
               ["Gross earnings", _m(t["gross"])], ["Levies", _m(t["levies"])], ["Other deductions", _m(t["other_deductions"])],
               ["Input loan deductions", _m(t["loan_deductions"])], ["Net payable", _m(t["net_payable"])],
               ["Amount paid", _m(t["paid"])], ["Unpaid balance", _m(t["unpaid"])], ["Loans still outstanding", _m(t["loans_outstanding"])]]
    tb = Table(summary, colWidths=[110 * mm, 60 * mm])
    tb.setStyle(grid)
    story += [tb, Spacer(1, 5 * mm)]
    for p in st["payouts"]:
        story.append(Paragraph(f"<b>{p.run.run_no}</b> · {p.run.crop.name} {p.run.season.name} · "
                               f"{'loss shared by farmers' if p.run.loss_policy == 'shared' else 'warehouse loss absorbed by AMCOS'}", small))
        rows = [["Item", "Qty / rate", "Amount"]]
        for l in p.lines:
            qty = f"{l.quantity:,.3f} kg x {l.rate:,.4f}" if l.line_type == "earning" else ""
            sign = "" if l.line_type == "earning" else "- "
            rows.append([Paragraph(l.description, small), qty, sign + _m(l.amount)])
        rows += [["Gross earnings", "", _m(p.gross_amount)], ["Total deductions", "", "- " + _m(p.total_deductions)],
                 ["NET PAYABLE", "", _m(p.net_payable)]]
        tb = Table(rows, colWidths=[95 * mm, 45 * mm, 35 * mm])
        tb.setStyle(grid)
        story += [tb, Spacer(1, 4 * mm)]
    if st["payments"]:
        rows = [["Date", "Status", "Reference", "Amount"]]
        for pay in st["payments"]:
            when = (pay.paid_at or pay.created_at).astimezone(tz).strftime("%d %b %Y")
            rows.append([when, pay.status, pay.transaction_ref or pay.failure_reason or "", _m(pay.amount)])
        tb = Table(rows, colWidths=[30 * mm, 25 * mm, 85 * mm, 35 * mm])
        tb.setStyle(grid)
        story += [Paragraph("<b>Payments</b>", small), tb]
    story += [Spacer(1, 5 * mm), Paragraph("Every figure is traceable to the delivery receipts, warehouse records and auction "
                                           "results held by the cooperative. Queries: contact your AMCOS office.", small)]
    doc.build(story)
    return buf.getvalue()
