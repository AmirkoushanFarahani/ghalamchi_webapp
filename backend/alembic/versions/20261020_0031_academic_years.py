"""Institute-scoped academic years and immutable enrollment grade/year snapshots.

Existing catalogs/registrations are assigned to the user-confirmed 1405/1406 year.
No amounts, payments, student identities or historical exam revisions are changed.
"""

from datetime import date
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20261020_0031"
down_revision = "20261015_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_academic_years",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "school_institute_id", sa.Uuid(), sa.ForeignKey("school_institutes.id"), nullable=False
        ),
        sa.Column("name", sa.String(9), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("school_institute_id", "name", name="uq_academic_year_school_name"),
        sa.CheckConstraint("starts_on <= ends_on", name="valid_academic_year_dates"),
    )
    for column in ("workspace_owner_id", "school_institute_id"):
        op.create_index(f"ix_school_academic_years_{column}", "school_academic_years", [column])
    table = sa.table(
        "school_academic_years",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_owner_id", sa.Uuid()),
        sa.column("school_institute_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("starts_on", sa.Date()),
        sa.column("ends_on", sa.Date()),
    )
    for school in (
        op.get_bind().execute(sa.text("SELECT id, manager_id FROM school_institutes")).mappings()
    ):
        for name, start, end in (
            ("1405/1406", date(2026, 9, 23), date(2027, 6, 21)),
            ("1406/1407", date(2027, 9, 23), date(2028, 6, 20)),
        ):
            op.get_bind().execute(
                table.insert().values(
                    id=uuid4(),
                    workspace_owner_id=school["manager_id"],
                    school_institute_id=school["id"],
                    name=name,
                    starts_on=start,
                    ends_on=end,
                )
            )
    for table_name in (
        "school_courses",
        "school_exam_plans",
        "school_exam_pricing_periods",
        "student_enrollments",
    ):
        op.add_column(
            table_name,
            sa.Column("academic_year", sa.String(9), nullable=False, server_default="1405/1406"),
        )
        op.create_index(f"ix_{table_name}_academic_year", table_name, ["academic_year"])
    op.add_column("student_enrollments", sa.Column("grade", sa.String(20), nullable=True))
    op.add_column("student_enrollments", sa.Column("academic_track", sa.String(100), nullable=True))
    op.add_column(
        "student_enrollments",
        sa.Column(
            "registration_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")
        ),
    )
    op.execute(
        sa.text("""UPDATE student_enrollments e SET grade=s.grade,
        academic_track=s.academic_track, registration_date=s.registration_date
        FROM students s WHERE s.id=e.student_id""")
    )
    for table_name, constraint, columns in (
        (
            "school_courses",
            "uq_school_course_workspace_name_grade",
            ["workspace_owner_id", "school_institute_id", "academic_year", "name", "grade"],
        ),
        (
            "school_exam_pricing_periods",
            "uq_exam_period_school_name",
            ["school_institute_id", "academic_year", "name"],
        ),
        (
            "school_exam_plans",
            "uq_school_exam_plan_period_revision",
            [
                "workspace_owner_id",
                "school_institute_id",
                "academic_year",
                "grade",
                "academic_track",
                "plan_code",
                "pricing_period_id",
                "revision",
            ],
        ),
    ):
        op.drop_constraint(constraint, table_name, type_="unique")
        kwargs = (
            {"postgresql_nulls_not_distinct": True} if table_name == "school_exam_plans" else {}
        )
        op.create_unique_constraint(constraint, table_name, columns, **kwargs)


def downgrade() -> None:
    raise RuntimeError("Academic-year history must not be merged by an automatic downgrade")
