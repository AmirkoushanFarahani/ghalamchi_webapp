"""Student class changes, instructor snapshots, credits and refund history."""

import sqlalchemy as sa

from alembic import op

revision = "20261014_0025"
down_revision = "20261001_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("enrollment_courses", sa.Column("instructor_name", sa.String(200), nullable=True))
    with op.batch_alter_table("enrollment_payments") as batch:
        batch.drop_constraint(
            op.f("ck_enrollment_payments_valid_enrollment_payment_status"), type_="check"
        )
        batch.create_check_constraint(
            "valid_enrollment_payment_status", "status IN ('PENDING','PAID','BOUNCED','CANCELLED')"
        )
    op.create_table(
        "enrollment_class_changes",
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
        sa.Column(
            "old_course_id",
            sa.Uuid(),
            sa.ForeignKey("school_courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "new_course_id",
            sa.Uuid(),
            sa.ForeignKey("school_courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("old_course_name", sa.String(200), nullable=False),
        sa.Column("new_course_name", sa.String(200), nullable=False),
        sa.Column("old_instructor_name", sa.String(200), nullable=True),
        sa.Column("new_instructor_name", sa.String(200), nullable=True),
        *(
            sa.Column(name, sa.Numeric(18, 2), nullable=False)
            for name in ("old_price", "new_price", "old_total", "new_total")
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("excess_handling", sa.String(10), nullable=False),
        sa.Column("refund_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("refund_status", sa.String(10), server_default="NONE", nullable=False),
        sa.Column("refund_method", sa.String(20), nullable=True),
        sa.Column("refunded_on", sa.Date(), nullable=True),
        sa.Column("refund_tracking_code", sa.String(100), nullable=True),
        sa.Column(
            "refunded_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint("refund_amount >= 0", name="nonnegative_class_change_refund"),
        sa.CheckConstraint(
            "excess_handling IN ('CREDIT','REFUND')", name="valid_class_change_excess_handling"
        ),
        sa.CheckConstraint(
            "refund_status IN ('NONE','PENDING','PAID','CANCELLED')",
            name="valid_class_change_refund_status",
        ),
        sa.CheckConstraint(
            "refund_method IS NULL OR refund_method IN ('CASH','BANK_TRANSFER')",
            name="valid_class_change_refund_method",
        ),
    )
    op.create_index(
        "ix_enrollment_class_changes_enrollment_id", "enrollment_class_changes", ["enrollment_id"]
    )


def downgrade() -> None:
    # Downgrading must not silently delete payment history or cancelled payments.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM enrollment_class_changes")):
        raise RuntimeError("Cannot downgrade while class-change history exists")
    if connection.scalar(
        sa.text("SELECT COUNT(*) FROM enrollment_payments WHERE status = 'CANCELLED'")
    ):
        raise RuntimeError("Cannot downgrade while cancelled payments exist")
    op.drop_table("enrollment_class_changes")
    with op.batch_alter_table("enrollment_payments") as batch:
        batch.drop_constraint(
            op.f("ck_enrollment_payments_valid_enrollment_payment_status"), type_="check"
        )
        batch.create_check_constraint(
            "valid_enrollment_payment_status", "status IN ('PENDING','PAID','BOUNCED')"
        )
    op.drop_column("enrollment_courses", "instructor_name")
