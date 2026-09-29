"""Add database timestamp defaults for manual school costs."""

import sqlalchemy as sa

from alembic import op


revision = "20260927_0022"
down_revision = "20260926_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "school_costs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "school_costs",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "school_costs",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
    op.alter_column(
        "school_costs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
