"""CSV and Excel payment-list exporters (generic columns).

The column layout is a sensible generic format. Each bank / mobile-money provider has its
own bulk-upload template; when the AMCOS supplies a real template, add an exporter for it
here rather than changing the payment workflow.
"""
import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Font

from app.integrations.payments.base import PaymentExporter, PaymentInstruction

HEADERS = ["payment_id", "reference", "membership_no", "farmer_name", "destination", "bank", "amount", "currency"]


def _rows(currency: str, items: list[PaymentInstruction]) -> list[list]:
    return [[i.payment_id, i.reference, i.membership_no, i.farmer_name, i.destination, i.destination_bank or "",
             f"{i.amount:.2f}", currency] for i in items]


class CsvExporter(PaymentExporter):
    file_extension, media_type = "csv", "text/csv"

    def __init__(self, method: str):
        self.method = method

    def render(self, batch_no: str, currency: str, instructions: list[PaymentInstruction]) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(HEADERS)
        w.writerows(_rows(currency, instructions))
        # utf-8-sig adds a BOM so Excel opens Swahili/accented names correctly
        return buf.getvalue().encode("utf-8-sig")


class ExcelExporter(PaymentExporter):
    file_extension = "xlsx"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def __init__(self, method: str):
        self.method = method

    def render(self, batch_no: str, currency: str, instructions: list[PaymentInstruction]) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = batch_no[:31]
        ws.append(HEADERS)
        for c in ws[1]:
            c.font = Font(bold=True)
        for row in _rows(currency, instructions):
            row[6] = float(row[6])  # numeric cell for totals in Excel (display only; source of truth is the DB)
            ws.append(row)
        ws.append([])
        ws.append(["TOTAL", "", "", f"{len(instructions)} payments", "", "", f"=SUM(G2:G{len(instructions) + 1})", currency])
        for col, width in zip("ABCDEFGH", (38, 22, 16, 30, 18, 18, 14, 8), strict=True):
            ws.column_dimensions[col].width = width
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()


def get_exporter(method: str, fmt: str) -> PaymentExporter:
    if fmt == "csv":
        return CsvExporter(method)
    if fmt == "xlsx":
        return ExcelExporter(method)
    raise ValueError(f"Unsupported export format {fmt}")
