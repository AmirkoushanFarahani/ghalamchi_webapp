"""Add manager-configured book and test fees to school registrations."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0019"
down_revision = "20260920_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_registration_fees",
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
        sa.Column("book_price", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("exam_price", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.CheckConstraint("book_price >= 0", name="nonnegative_school_book_price"),
        sa.CheckConstraint("exam_price >= 0", name="nonnegative_school_exam_price"),
        sa.ForeignKeyConstraint(["workspace_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_owner_id", name="uq_school_registration_fees_workspace"),
    )
    op.create_index(
        "ix_school_registration_fees_workspace_owner_id",
        "school_registration_fees",
        ["workspace_owner_id"],
    )
    op.add_column(
        "student_enrollments",
        sa.Column("book_price", sa.Numeric(18, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "student_enrollments",
        sa.Column("exam_price", sa.Numeric(18, 2), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("student_enrollments", "exam_price")
    op.drop_column("student_enrollments", "book_price")
    op.drop_index(
        "ix_school_registration_fees_workspace_owner_id",
        table_name="school_registration_fees",
    )
    op.drop_table("school_registration_fees")
