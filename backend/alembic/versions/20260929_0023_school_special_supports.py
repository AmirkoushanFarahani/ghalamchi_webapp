"""Add school special support catalog and enrollment add-on columns."""

import sqlalchemy as sa

from alembic import op

revision = "20260929_0023"
down_revision = "20260927_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_special_supports",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.Column("workspace_owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("monthly_price", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("seasonal_price", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "monthly_price >= 0", name="nonnegative_school_special_support_monthly"
        ),
        sa.CheckConstraint(
            "seasonal_price >= 0", name="nonnegative_school_special_support_seasonal"
        ),
        sa.ForeignKeyConstraint(["workspace_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_owner_id", "name", name="uq_school_special_support_workspace_name"
        ),
    )
    op.create_index(
        "ix_school_special_supports_workspace_owner_id",
        "school_special_supports",
        ["workspace_owner_id"],
    )
    op.add_column(
        "student_enrollments",
        sa.Column("special_support_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "student_enrollments",
        sa.Column("special_support_period", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "student_enrollments",
        sa.Column(
            "special_support_price", sa.Numeric(18, 2), server_default="0", nullable=False
        ),
    )
    op.create_check_constraint(
        "valid_enrollment_special_support_period",
        "student_enrollments",
        "special_support_period IS NULL OR "
        "special_support_period IN ('MONTHLY','SEASONAL')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "valid_enrollment_special_support_period", "student_enrollments", type_="check"
    )
    op.drop_column("student_enrollments", "special_support_price")
    op.drop_column("student_enrollments", "special_support_period")
    op.drop_column("student_enrollments", "special_support_name")
    op.drop_index(
        "ix_school_special_supports_workspace_owner_id", table_name="school_special_supports"
    )
    op.drop_table("school_special_supports")
