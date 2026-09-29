"""Add grade and major specific school exam plans."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0021"
down_revision = "20260926_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_exam_plans",
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
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("academic_track", sa.String(length=100), nullable=True),
        sa.Column("plan_code", sa.String(length=30), nullable=False),
        sa.Column("exam_count", sa.Integer(), nullable=False),
        sa.Column("exam_unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("exam_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("book_voucher_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("book_voucher_discount", sa.Numeric(18, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "grade IN ('GRADE_1','GRADE_2','GRADE_3','GRADE_4','GRADE_5','GRADE_6',"
            "'GRADE_7','GRADE_8','GRADE_9','GRADE_10','GRADE_11','GRADE_12')",
            name="valid_school_exam_plan_grade",
        ),
        sa.CheckConstraint("exam_count > 0", name="positive_school_exam_plan_count"),
        sa.CheckConstraint("exam_unit_price >= 0", name="nonnegative_school_exam_plan_unit_price"),
        sa.CheckConstraint("exam_total >= 0", name="nonnegative_school_exam_plan_total"),
        sa.CheckConstraint(
            "book_voucher_amount >= 0", name="nonnegative_school_exam_plan_book_amount"
        ),
        sa.CheckConstraint(
            "book_voucher_discount >= 0", name="nonnegative_school_exam_plan_book_discount"
        ),
        sa.CheckConstraint(
            "book_voucher_discount <= book_voucher_amount",
            name="school_exam_plan_discount_within_book_amount",
        ),
        sa.ForeignKeyConstraint(["workspace_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_owner_id",
            "grade",
            "academic_track",
            "plan_code",
            name="uq_school_exam_plan_workspace_grade_track_code",
        ),
    )
    op.create_index(
        "ix_school_exam_plans_workspace_owner_id", "school_exam_plans", ["workspace_owner_id"]
    )
    op.create_index("ix_school_exam_plans_grade", "school_exam_plans", ["grade"])
    op.create_index("ix_school_exam_plans_academic_track", "school_exam_plans", ["academic_track"])
    op.add_column("student_enrollments", sa.Column("exam_plan_id", sa.Uuid(), nullable=True))
    op.add_column(
        "student_enrollments", sa.Column("exam_plan_code", sa.String(length=30), nullable=True)
    )
    op.add_column(
        "student_enrollments",
        sa.Column("book_voucher_discount", sa.Numeric(18, 2), server_default="0", nullable=False),
    )
    op.create_foreign_key(
        "fk_student_enrollments_exam_plan_id_school_exam_plans",
        "student_enrollments",
        "school_exam_plans",
        ["exam_plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_student_enrollments_exam_plan_id_school_exam_plans",
        "student_enrollments",
        type_="foreignkey",
    )
    op.drop_column("student_enrollments", "book_voucher_discount")
    op.drop_column("student_enrollments", "exam_plan_code")
    op.drop_column("student_enrollments", "exam_plan_id")
    op.drop_index("ix_school_exam_plans_academic_track", table_name="school_exam_plans")
    op.drop_index("ix_school_exam_plans_grade", table_name="school_exam_plans")
    op.drop_index("ix_school_exam_plans_workspace_owner_id", table_name="school_exam_plans")
    op.drop_table("school_exam_plans")
