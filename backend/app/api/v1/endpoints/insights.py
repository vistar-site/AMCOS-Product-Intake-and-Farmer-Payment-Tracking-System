"""Dashboard, reports, audit trail, notifications, settings and sync review."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models import Organization, User
from app.services import audit_query_service, dashboard_service, finance_service, notification_service, report_service
from app.services import settings_service
from app.services.scope import org_id
from app.services.statement_pdf import render_statement

router = APIRouter()
db_dep = Depends(get_db)


def exact(obj):
    """Endpoints without a response_model would let FastAPI turn Decimal into float
    (2001000.00 -> 2001000.0, and worse for large or fractional values). Money and weights
    must stay exact, so convert every Decimal to its exact string first."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: exact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [exact(v) for v in obj]
    return obj


# ---------------- dashboard
@router.get("/dashboard", tags=["dashboard"])
def dashboard(date_from: datetime | None = None, date_to: datetime | None = None, crop_id: uuid.UUID | None = None,
              centre_id: uuid.UUID | None = None, u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    return exact(dashboard_service.dashboard(db, u, date_from=date_from, date_to=date_to, crop_id=crop_id, centre_id=centre_id))


# ---------------- reports
def _filters(date_from: date | None = None, date_to: date | None = None, crop_id: uuid.UUID | None = None,
             centre_id: uuid.UUID | None = None, season_id: uuid.UUID | None = None,
             farmer_id: uuid.UUID | None = None) -> report_service.Filters:
    return report_service.Filters(date_from, date_to, crop_id, centre_id, season_id, farmer_id)


@router.get("/reports", tags=["reports"])
def report_catalogue(u: User = Depends(require_permission("delivery.view"))):
    return report_service.catalogue(u)


@router.get("/reports/{code}", tags=["reports"])
def report_preview(code: str, f: report_service.Filters = Depends(_filters),
                   u: User = Depends(require_permission("delivery.view")), db: Session = db_dep):
    r = report_service.run(db, u, code, f)
    return exact({"code": r.code, "title": r.title, "filters_text": r.filters_text, "generated_at": r.generated_at,
                  "columns": [c.__dict__ for c in r.columns], "rows": r.rows[:1000], "row_count": len(r.rows),
                  "truncated": len(r.rows) > 1000, "totals": r.totals})


@router.get("/reports/{code}/export", tags=["reports"])
def report_export(code: str, format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
                  f: report_service.Filters = Depends(_filters), u: User = Depends(require_permission("delivery.view")),
                  db: Session = db_dep):
    r = report_service.run(db, u, code, f)
    org = db.get(Organization, org_id(u))
    tz = ZoneInfo(org.timezone)
    if format == "csv":
        data, media = report_service.to_csv(r, tz), "text/csv"
    elif format == "xlsx":
        data, media = report_service.to_xlsx(r, tz), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        data, media = report_service.to_pdf(r, org), "application/pdf"
    name = f"{code}-{r.generated_at.astimezone(tz):%Y%m%d-%H%M}.{format}"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/farmers/{farmer_id}/statement.pdf", tags=["reports"])
def statement_pdf(farmer_id: uuid.UUID, u: User = Depends(require_permission("farmer.view_financial")), db: Session = db_dep):
    st = finance_service.farmer_statement(db, u, farmer_id)
    pdf = render_statement(st, db.get(Organization, org_id(u)))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="statement-{st["farmer"].membership_no}.pdf"'})


# ---------------- audit trail
@router.get("/audit-logs", tags=["audit"])
def audit_logs(action: str | None = Query(None, max_length=100), entity_type: str | None = None, entity_id: str | None = None,
               user_id: uuid.UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
               q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
               u: User = Depends(require_permission("audit.view")), db: Session = db_dep):
    rows, total = audit_query_service.list_audit(db, u, action=action, entity_type=entity_type, entity_id=entity_id,
                                                 user_id=user_id, date_from=date_from, date_to=date_to, q=q,
                                                 page=page, page_size=page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": a.id, "created_at": a.created_at, "user_id": a.user_id, "user_name": name, "action": a.action,
         "entity_type": a.entity_type, "entity_id": a.entity_id, "before": a.before, "after": a.after,
         "reason": a.reason, "ip_address": a.ip_address} for a, name in rows]}


@router.get("/audit-logs/actions", tags=["audit"])
def audit_actions(u: User = Depends(require_permission("audit.view")), db: Session = db_dep):
    return audit_query_service.audit_actions(db, u)


# ---------------- sync review (offline conflicts / rejections)
@router.get("/sync/problems", tags=["sync"])
def sync_problems(u: User = Depends(require_permission("delivery.amend_approve")), db: Session = db_dep):
    return [{"id": s.id, "created_at": s.created_at, "user_name": name, "device_id": s.device_id, "received": s.received,
             "created": s.created, "duplicates": s.duplicates, "conflicts": s.conflicts, "rejected": s.rejected,
             "details": s.details} for s, name in audit_query_service.sync_problems(db, u)]


# ---------------- notifications
@router.get("/notifications/messages", tags=["notifications"])
def messages(status: str | None = Query(None, pattern="^(queued|sent|delivered|failed|simulated|cancelled)$"),
             farmer_id: uuid.UUID | None = None, q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1),
             page_size: int = Query(50, ge=1, le=200), u: User = Depends(require_permission("notification.manage")),
             db: Session = db_dep):
    items, total = notification_service.list_messages(db, org_id(u), status=status, farmer_id=farmer_id, q=q,
                                                      page=page, page_size=page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": m.id, "created_at": m.created_at, "phone": m.phone, "farmer_id": m.farmer_id, "template_code": m.template_code,
         "body": m.body, "status": m.status, "provider": m.provider, "attempts": m.attempts, "last_error": m.last_error,
         "sent_at": m.sent_at, "next_attempt_at": m.next_attempt_at, "related_type": m.related_type,
         "related_id": m.related_id} for m in items]}


@router.post("/notifications/messages/{message_id}/retry", tags=["notifications"])
def retry(message_id: uuid.UUID, background: BackgroundTasks, u: User = Depends(require_permission("notification.manage")),
          db: Session = db_dep):
    m = notification_service.retry_message(db, u, org_id(u), message_id)
    background.add_task(notification_service.process_queue_background, u.organization_id)
    return {"id": m.id, "status": m.status}


@router.post("/notifications/process", tags=["notifications"])
def process(u: User = Depends(require_permission("notification.manage")), db: Session = db_dep):
    return notification_service.process_queue(db, org_id(u))


@router.get("/notifications/templates", tags=["notifications"])
def templates(u: User = Depends(require_permission("notification.manage")), db: Session = db_dep):
    return notification_service.list_templates(db, org_id(u))


class TemplateBody(BaseModel):
    body: str = Field(min_length=10, max_length=480)


@router.put("/notifications/templates/{code}/{language}", tags=["notifications"])
def save_template(code: str, language: str, body: TemplateBody, u: User = Depends(require_permission("notification.manage")),
                  db: Session = db_dep):
    return notification_service.save_template(db, u, org_id(u), code, language, body.body)


# ---------------- settings
@router.get("/settings", tags=["settings"])
def get_settings(u: User = Depends(require_permission("centre.view")), db: Session = db_dep):
    return settings_service.all_settings(db, org_id(u))


class SettingsBody(BaseModel):
    values: dict[str, Any]


@router.put("/settings", tags=["settings"])
def put_settings(body: SettingsBody, u: User = Depends(require_permission("settings.manage")), db: Session = db_dep):
    return settings_service.update_settings(db, u, org_id(u), body.values)
