"""Optional mother contact details; existing guardian columns retain father values."""

import sqlalchemy as sa

from alembic import op

revision = "20261022_0034"
down_revision = "20261021_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("students", sa.Column("mother_full_name", sa.String(200), nullable=True))
    op.add_column("students", sa.Column("mother_phone", sa.String(32), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Review/export mother contact information before a destructive rollback")
