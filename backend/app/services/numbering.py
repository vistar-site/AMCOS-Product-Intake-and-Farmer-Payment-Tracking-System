"""Human-readable sequential numbers (receipts, batches) that never collide.

How it works inside the caller's transaction:
1. INSERT the counter row if missing (ON CONFLICT DO NOTHING handles a race).
2. SELECT ... FOR UPDATE locks that row: a second clerk saving at the same moment
   WAITS here until the first transaction commits or rolls back.
3. Read the value, increment, and the lock is released at commit.
If the transaction rolls back, the increment rolls back too — no gaps from failures.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import NumberSequence


def next_number(db: Session, organization_id: uuid.UUID, sequence_key: str) -> int:
    db.execute(insert(NumberSequence)
               .values(organization_id=organization_id, sequence_key=sequence_key, next_value=1)
               .on_conflict_do_nothing())
    seq = db.execute(select(NumberSequence)
                     .where(NumberSequence.organization_id == organization_id,
                            NumberSequence.sequence_key == sequence_key)
                     .with_for_update()).scalar_one()
    value = seq.next_value
    seq.next_value = value + 1
    return value


def delivery_receipt_no(db: Session, organization_id: uuid.UUID, org_code: str, year: int) -> str:
    """e.g. DEMO-2026-000042 (numbering restarts every calendar year)."""
    n = next_number(db, organization_id, f"delivery:{year}")
    return f"{org_code}-{year}-{n:06d}"
