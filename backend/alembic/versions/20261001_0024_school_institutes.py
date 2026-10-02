"""Add isolated manager schools and move existing school data into a default school."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "20261001_0024"
down_revision = "20260929_0023"
branch_labels = None
depends_on = None


SCHOOL_TABLES = (
    "school_courses",
    "school_discount_codes",
    "school_registration_fees",
    "school_exam_plans",
    "school_special_supports",
    "students",
    "student_enrollments",
    "enrollment_payments",
    "school_costs",
)


def upgrade() -> None:
    op.create_table(
        "school_institutes",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("manager_id", "name", name="uq_school_institute_manager_name"),
    )
    op.create_index("ix_school_institutes_manager_id", "school_institutes", ["manager_id"])
    op.add_column("users", sa.Column("school_institute_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("active_school_institute_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_users_school_institute_id", "users", "school_institutes", ["school_institute_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_users_active_school_institute_id", "users", "school_institutes", ["active_school_institute_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_users_school_institute_id", "users", ["school_institute_id"])
    op.create_index("ix_users_active_school_institute_id", "users", ["active_school_institute_id"])
    for table in SCHOOL_TABLES:
        op.add_column(table, sa.Column("school_institute_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(f"fk_{table}_school_institute_id", table, "school_institutes", ["school_institute_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_school_institute_id", table, ["school_institute_id"])

    bind = op.get_bind()
    owner_rows = bind.execute(sa.text("""
        SELECT id FROM users WHERE business_category = 'EDUCATION' AND school_manager_id IS NULL
        UNION SELECT DISTINCT school_manager_id FROM users WHERE school_manager_id IS NOT NULL
        UNION SELECT DISTINCT workspace_owner_id FROM students
    """)).scalars().all()
    schools: dict[object, object] = {}
    for owner_id in owner_rows:
        school_id = uuid4()
        schools[owner_id] = school_id
        bind.execute(
            sa.text("INSERT INTO school_institutes (id, manager_id, name, is_active) VALUES (:id, :manager_id, :name, true)"),
            {"id": school_id, "manager_id": owner_id, "name": "آموزشگاه اول"},
        )
        bind.execute(sa.text("UPDATE users SET active_school_institute_id = :school_id WHERE id = :manager_id"), {"school_id": school_id, "manager_id": owner_id})
        bind.execute(sa.text("UPDATE users SET school_institute_id = :school_id WHERE school_manager_id = :manager_id"), {"school_id": school_id, "manager_id": owner_id})
        for table in SCHOOL_TABLES:
            bind.execute(sa.text(f"UPDATE {table} SET school_institute_id = :school_id WHERE workspace_owner_id = :manager_id"), {"school_id": school_id, "manager_id": owner_id})

    unique_constraints = (
        ("school_courses", "uq_school_course_workspace_name_grade", ["workspace_owner_id", "school_institute_id", "name", "grade"]),
        ("school_discount_codes", "uq_school_discount_workspace_code", ["workspace_owner_id", "school_institute_id", "code"]),
        ("school_registration_fees", "uq_school_registration_fees_workspace", ["workspace_owner_id", "school_institute_id"]),
        ("school_exam_plans", "uq_school_exam_plan_workspace_grade_track_code", ["workspace_owner_id", "school_institute_id", "grade", "academic_track", "plan_code"]),
        ("school_special_supports", "uq_school_special_support_workspace_name", ["workspace_owner_id", "school_institute_id", "name"]),
        ("students", "uq_student_workspace_national_id", ["workspace_owner_id", "school_institute_id", "national_id"]),
        ("school_costs", "uq_school_cost_workspace_factor_number", ["workspace_owner_id", "school_institute_id", "factor_number"]),
    )
    for table, name, columns in unique_constraints:
        op.drop_constraint(name, table, type_="unique")
        op.create_unique_constraint(name, table, columns)


def downgrade() -> None:
    unique_constraints = (
        ("school_courses", "uq_school_course_workspace_name_grade", ["workspace_owner_id", "name", "grade"]),
        ("school_discount_codes", "uq_school_discount_workspace_code", ["workspace_owner_id", "code"]),
        ("school_registration_fees", "uq_school_registration_fees_workspace", ["workspace_owner_id"]),
        ("school_exam_plans", "uq_school_exam_plan_workspace_grade_track_code", ["workspace_owner_id", "grade", "academic_track", "plan_code"]),
        ("school_special_supports", "uq_school_special_support_workspace_name", ["workspace_owner_id", "name"]),
        ("students", "uq_student_workspace_national_id", ["workspace_owner_id", "national_id"]),
        ("school_costs", "uq_school_cost_workspace_factor_number", ["workspace_owner_id", "factor_number"]),
    )
    for table, name, columns in unique_constraints:
        op.drop_constraint(name, table, type_="unique")
        op.create_unique_constraint(name, table, columns)
    for table in reversed(SCHOOL_TABLES):
        op.drop_index(f"ix_{table}_school_institute_id", table_name=table)
        op.drop_constraint(f"fk_{table}_school_institute_id", table, type_="foreignkey")
        op.drop_column(table, "school_institute_id")
    op.drop_index("ix_users_active_school_institute_id", table_name="users")
    op.drop_index("ix_users_school_institute_id", table_name="users")
    op.drop_constraint("fk_users_active_school_institute_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_school_institute_id", "users", type_="foreignkey")
    op.drop_column("users", "active_school_institute_id")
    op.drop_column("users", "school_institute_id")
    op.drop_index("ix_school_institutes_manager_id", table_name="school_institutes")
    op.drop_table("school_institutes")
