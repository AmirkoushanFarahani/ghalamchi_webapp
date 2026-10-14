"""Persist auditable student special-support replacements."""

import sqlalchemy as sa

from alembic import op

revision = "20261014_0027"
down_revision = "20261014_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrollment_support_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("student_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "changed_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("old_name", sa.String(200), nullable=True),
        sa.Column("old_period", sa.String(20), nullable=True),
        sa.Column("old_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("new_name", sa.String(200), nullable=False),
        sa.Column("new_period", sa.String(20), nullable=False),
        sa.Column("new_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("old_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("new_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.CheckConstraint(
            "old_price >= 0 AND new_price >= 0", name="nonnegative_support_change_prices"
        ),
    )
    op.create_index(
        "ix_enrollment_support_changes_enrollment_id",
        "enrollment_support_changes",
        ["enrollment_id"],
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM enrollment_support_changes")):
        raise RuntimeError("Cannot downgrade while special-support change history exists")
    op.drop_table("enrollment_support_changes")
