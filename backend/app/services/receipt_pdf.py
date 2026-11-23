"""PDF delivery receipt (A6-ish, printable on small thermal or A4 printers)."""
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models import Delivery, Organization


def render_receipt(delivery: Delivery, org: Organization) -> bytes:
    buf = BytesIO()
    w, h = A6
    c = canvas.Canvas(buf, pagesize=A6)
    c.setTitle(f"Receipt {delivery.receipt_no}")
    tz = ZoneInfo(org.timezone)
    y = h - 12 * mm

    def line(label: str, value: str, bold: bool = False):
        nonlocal y
        c.setFont("Helvetica", 7.5)
        c.drawString(8 * mm, y, label)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 8.5 if bold else 8)
        c.drawRightString(w - 8 * mm, y, value[:48])
        y -= 5 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(w / 2, y, org.name[:45])
    y -= 4.5 * mm
    c.setFont("Helvetica", 7)
    if org.registration_no:
        c.drawCentredString(w / 2, y, f"Reg. No. {org.registration_no}")
        y -= 4 * mm
    if org.is_demo:
        c.setFillColorRGB(0.8, 0, 0)
        c.drawCentredString(w / 2, y, "DEMONSTRATION DATA — NOT A VALID RECEIPT")
        c.setFillColorRGB(0, 0, 0)
        y -= 4 * mm
    y -= 2 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, y, "PRODUCE DELIVERY RECEIPT")
    y -= 7 * mm

    line("Receipt No.", delivery.receipt_no, bold=True)
    if delivery.provisional_receipt_no:
        line("Offline ref.", delivery.provisional_receipt_no)
    line("Date & time", delivery.captured_at.astimezone(tz).strftime("%d %b %Y %H:%M"))
    y -= 1.5 * mm
    line("Farmer", delivery.farmer.full_name)
    line("Membership No.", delivery.farmer.membership_no)
    line("Collection point", delivery.centre.name)
    y -= 1.5 * mm
    line("Crop", delivery.crop.name + (f" ({delivery.grade.code})" if delivery.grade else ""))
    line("Season", delivery.season.name)
    line("Gross weight", f"{delivery.gross_weight:,.3f} {delivery.unit}")
    line("Tare weight", f"{delivery.tare_weight:,.3f} {delivery.unit}")
    line("NET WEIGHT", f"{delivery.net_weight:,.3f} {delivery.unit}", bold=True)
    y -= 1.5 * mm
    line("Received by", delivery.recorder.full_name)
    if delivery.status == "voided":
        c.setFillColorRGB(0.8, 0, 0)
        c.setFont("Helvetica-Bold", 22)
        c.saveState()
        c.translate(w / 2, h / 2)
        c.rotate(30)
        c.drawCentredString(0, 0, "VOIDED")
        c.restoreState()
        c.setFillColorRGB(0, 0, 0)

    y -= 3 * mm
    c.setFont("Helvetica", 6.5)
    c.drawString(8 * mm, y, "Verification reference:")
    y -= 3.5 * mm
    c.setFont("Courier", 6.5)
    c.drawString(8 * mm, y, str(delivery.id))
    y -= 5 * mm
    c.setFont("Helvetica-Oblique", 6.5)
    c.drawString(8 * mm, y, "Keep this receipt. Payment follows sale of the produce at auction.")
    c.showPage()
    c.save()
    return buf.getvalue()
