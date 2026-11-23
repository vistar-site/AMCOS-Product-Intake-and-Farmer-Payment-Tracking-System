"""batch member added_at server default

Revision ID: 65573807367a
Revises: cc3406930aa9
Create Date: 2026-11-23 07:08:26.275997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65573807367a'
down_revision: Union[str, Sequence[str], None] = 'cc3406930aa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Hand-written: autogenerate does not compare server defaults."""
    op.alter_column("batch_deliveries", "added_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("batch_deliveries", "added_at", server_default=None)
