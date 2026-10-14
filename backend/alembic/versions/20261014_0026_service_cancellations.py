"""Add attendance-backed service cancellation and refund records."""

import sqlalchemy as sa

from alembic import op

revision = "20261014_0026"
down_revision = "20261014_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "school_courses",
        sa.Column("session_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "nonnegative_school_course_session_count",
        "school_courses",
        "session_count >= 0",
    )
    op.add_column(
        "student_enrollments",
        sa.Column("exam_session_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "enrollment_courses",
        sa.Column("session_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "enrollment_courses",
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
    )
    op.create_check_constraint(
        "valid_enrollment_course_status",
        "enrollment_courses",
        "status IN ('ACTIVE','CANCELLED')",
    )
    op.create_table(
        "enrollment_service_attendance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), sa.ForeignKey("student_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("school_courses.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("service_key", sa.String(80), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("attended_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.UniqueConstraint("enrollment_id", "service_key", "session_number", name="uq_enrollment_service_attendance_session"),
        sa.CheckConstraint("service_type IN ('COURSE','EXAM')", name="valid_attendance_service_type"),
        sa.CheckConstraint("session_number > 0", name="positive_attendance_session_number"),
    )
    op.create_index("ix_enrollment_service_attendance_enrollment_id", "enrollment_service_attendance", ["enrollment_id"])
    op.create_table(
        "enrollment_service_cancellations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), sa.ForeignKey("student_enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("school_courses.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("service_key", sa.String(80), nullable=False),
        sa.Column("service_name", sa.String(200), nullable=False),
        *[sa.Column(name, sa.Numeric(18, 2), nullable=False) for name in ("original_price", "attendance_charge", "cancellation_fee", "retained_amount", "old_total", "new_total")],
        sa.Column("total_sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attended_sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("excess_handling", sa.String(10), nullable=False),
        sa.Column("refund_amount", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("refund_status", sa.String(10), server_default="NONE", nullable=False),
        sa.Column("refund_method", sa.String(20), nullable=True),
        sa.Column("refunded_on", sa.Date(), nullable=True),
        sa.Column("refund_tracking_code", sa.String(100), nullable=True),
        sa.Column("refunded_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.UniqueConstraint("enrollment_id", "service_key", name="uq_enrollment_service_cancellation"),
        sa.CheckConstraint("service_type IN ('COURSE','EXAM','BOOK','SUPPORT')", name="valid_cancellation_service_type"),
        sa.CheckConstraint("total_sessions >= 0 AND attended_sessions >= 0", name="nonnegative_cancellation_sessions"),
        sa.CheckConstraint("attended_sessions <= total_sessions", name="cancellation_sessions_within_total"),
        sa.CheckConstraint("original_price >= 0 AND attendance_charge >= 0 AND cancellation_fee >= 0 AND retained_amount >= 0 AND refund_amount >= 0", name="nonnegative_cancellation_amounts"),
        sa.CheckConstraint("refund_status IN ('NONE','PENDING','PAID','CANCELLED')", name="valid_cancellation_refund_status"),
        sa.CheckConstraint("refund_method IS NULL OR refund_method IN ('CASH','BANK_TRANSFER')", name="valid_cancellation_refund_method"),
    )
    op.create_index("ix_enrollment_service_cancellations_enrollment_id", "enrollment_service_cancellations", ["enrollment_id"])


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM enrollment_service_attendance")) or connection.scalar(sa.text("SELECT COUNT(*) FROM enrollment_service_cancellations")):
        raise RuntimeError("Cannot downgrade while attendance or cancellation history exists")
    op.drop_table("enrollment_service_cancellations")
    op.drop_table("enrollment_service_attendance")
    op.drop_constraint("valid_enrollment_course_status", "enrollment_courses", type_="check")
    op.drop_column("enrollment_courses", "status")
    op.drop_column("enrollment_courses", "session_count")
    op.drop_column("student_enrollments", "exam_session_count")
    op.drop_constraint("nonnegative_school_course_session_count", "school_courses", type_="check")
    op.drop_column("school_courses", "session_count")
