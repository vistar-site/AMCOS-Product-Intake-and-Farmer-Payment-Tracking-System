"""Per-AMCOS configurable settings with typed definitions and safe defaults.

Only keys defined in SETTINGS can be stored, and values are validated against their type,
so a typo can't silently create a useless setting.
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailedError
from app.models import Setting, User
from app.services import audit_service


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    type: str          # 'bool' | 'decimal' | 'int' | 'str' | 'choice'
    default: Any
    group: str
    help: str = ""
    choices: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None


SETTINGS: dict[str, SettingDef] = {d.key: d for d in [
    SettingDef("warehouse.discrepancy_tolerance_percent", "Discrepancy tolerance (%)", "decimal", "0.5", "Warehouse",
               "Weight differences up to this % are recorded but auto-accepted.", min=0, max=10),
    SettingDef("sms.enabled", "Send SMS notifications", "bool", True, "SMS",
               "Master switch for all farmer SMS."),
    SettingDef("sms.delivery_receipt", "SMS receipt after each delivery", "bool", True, "SMS"),
    SettingDef("sms.payment_confirmation", "SMS when a payment is confirmed", "bool", True, "SMS"),
    SettingDef("sms.language", "SMS language", "choice", "sw", "SMS", choices=("sw", "en")),
    SettingDef("sms.max_attempts", "Maximum send attempts", "int", 3, "SMS", min=1, max=10),
    SettingDef("receipts.footer", "Receipt footer text", "str", "Keep this receipt. Payment follows sale at auction.",
               "Receipts"),
]}

# Kept for backwards compatibility with Phase 6 code
DEFAULTS = {k: d.default for k, d in SETTINGS.items()}


def _coerce(d: SettingDef, value: Any) -> Any:
    try:
        if d.type == "bool":
            if not isinstance(value, bool):
                raise ValueError
            return value
        if d.type == "decimal":
            v = Decimal(str(value))
            if (d.min is not None and v < Decimal(str(d.min))) or (d.max is not None and v > Decimal(str(d.max))):
                raise ValueError
            return str(v)
        if d.type == "int":
            v = int(value)
            if (d.min is not None and v < d.min) or (d.max is not None and v > d.max):
                raise ValueError
            return v
        if d.type == "choice":
            if value not in d.choices:
                raise ValueError
            return value
        v = str(value)
        if len(v) > 300:
            raise ValueError
        return v
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValidationFailedError(f"Invalid value for '{d.label}'") from exc


def get_setting(db: Session, organization_id: uuid.UUID, key: str) -> Any:
    row = db.scalar(select(Setting).where(Setting.organization_id == organization_id, Setting.key == key))
    return row.value if row is not None else SETTINGS[key].default


def all_settings(db: Session, organization_id: uuid.UUID) -> list[dict]:
    stored = {s.key: s.value for s in db.scalars(select(Setting).where(Setting.organization_id == organization_id))}
    return [{"key": d.key, "label": d.label, "type": d.type, "group": d.group, "help": d.help,
             "choices": list(d.choices), "min": d.min, "max": d.max, "default": d.default,
             "value": stored.get(d.key, d.default)} for d in SETTINGS.values()]


def update_settings(db: Session, actor: User, organization_id: uuid.UUID, values: dict[str, Any]) -> list[dict]:
    unknown = set(values) - set(SETTINGS)
    if unknown:
        raise ValidationFailedError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
    before, after = {}, {}
    for key, raw in values.items():
        v = _coerce(SETTINGS[key], raw)
        row = db.scalar(select(Setting).where(Setting.organization_id == organization_id, Setting.key == key))
        old = row.value if row else SETTINGS[key].default
        if old == v:
            continue
        if row:
            row.value = v
        else:
            db.add(Setting(organization_id=organization_id, key=key, value=v))
        before[key], after[key] = old, v
    if after:
        audit_service.record(db, action="settings.update", user_id=actor.id, organization_id=organization_id,
                             entity_type="settings", before=before, after=after)
    db.commit()
    return all_settings(db, organization_id)


def tolerance_percent(db: Session, organization_id: uuid.UUID) -> Decimal:
    return Decimal(str(get_setting(db, organization_id, "warehouse.discrepancy_tolerance_percent")))
