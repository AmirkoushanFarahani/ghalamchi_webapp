"""Add timestamp defaults to registration fee settings."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0020"
down_revision = "20260926_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "school_registration_fees",
        "created_at",
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "school_registration_fees",
        "updated_at",
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def downgrade() -> None:
    op.alter_column("school_registration_fees", "updated_at", server_default=None)
    op.alter_column("school_registration_fees", "created_at", server_default=None)
