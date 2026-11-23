"""Per-AMCOS configurable settings with safe defaults (nothing business-critical hardcoded)."""
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting

DEFAULTS: dict[str, Any] = {
    # Differences up to this % of the expected weight are recorded but auto-accepted
    # (scale variation, moisture). Larger differences stay "open" until explained.
    "warehouse.discrepancy_tolerance_percent": "0.5",
}


def get_setting(db: Session, organization_id: uuid.UUID, key: str) -> Any:
    row = db.scalar(select(Setting).where(Setting.organization_id == organization_id, Setting.key == key))
    return row.value if row else DEFAULTS[key]


def tolerance_percent(db: Session, organization_id: uuid.UUID) -> Decimal:
    return Decimal(str(get_setting(db, organization_id, "warehouse.discrepancy_tolerance_percent")))
