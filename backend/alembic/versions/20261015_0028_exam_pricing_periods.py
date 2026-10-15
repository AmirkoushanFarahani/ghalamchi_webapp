"""Preserve exam price versions and group them into school pricing periods."""

import sqlalchemy as sa

from alembic import op

revision = "20261015_0028"
down_revision = "20261014_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_exam_pricing_periods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "workspace_owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "school_institute_id",
            sa.Uuid(),
            sa.ForeignKey("school_institutes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.UniqueConstraint("school_institute_id", "name", name="uq_exam_period_school_name"),
        sa.CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on",
            name="valid_exam_pricing_period_dates",
        ),
    )
    op.create_index(
        "ix_school_exam_pricing_periods_school_institute_id",
        "school_exam_pricing_periods",
        ["school_institute_id"],
    )
    op.add_column("school_exam_plans", sa.Column("pricing_period_id", sa.Uuid(), nullable=True))
    op.add_column(
        "school_exam_plans", sa.Column("revision", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column(
        "school_exam_plans",
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_foreign_key(
        "fk_exam_plan_pricing_period",
        "school_exam_plans",
        "school_exam_pricing_periods",
        ["pricing_period_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_school_exam_plans_pricing_period_id", "school_exam_plans", ["pricing_period_id"]
    )
    op.drop_constraint(
        "uq_school_exam_plan_workspace_grade_track_code", "school_exam_plans", type_="unique"
    )
    # PostgreSQL historically allowed duplicate NULL-track plans. Preserve all of
    # them as revisions rather than deleting any records referenced by students.
    op.execute(
        sa.text("""
        WITH numbered AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY workspace_owner_id, school_institute_id,
                                    grade, academic_track, plan_code
                       ORDER BY created_at, id
                   ) AS rev,
                   row_number() OVER (
                       PARTITION BY workspace_owner_id, school_institute_id,
                                    grade, academic_track, plan_code
                       ORDER BY created_at DESC, id DESC
                   ) AS newest
            FROM school_exam_plans
        )
        UPDATE school_exam_plans p SET revision = n.rev, is_current = (n.newest = 1)
        FROM numbered n WHERE p.id = n.id
    """)
    )
    op.create_unique_constraint(
        "uq_school_exam_plan_period_revision",
        "school_exam_plans",
        [
            "workspace_owner_id",
            "school_institute_id",
            "grade",
            "academic_track",
            "plan_code",
            "pricing_period_id",
            "revision",
        ],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM school_exam_pricing_periods")
    ) or op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM school_exam_plans WHERE revision > 1")):
        raise RuntimeError("Cannot downgrade while dated exam prices or price history exist")
    op.drop_constraint("uq_school_exam_plan_period_revision", "school_exam_plans", type_="unique")
    op.create_unique_constraint(
        "uq_school_exam_plan_workspace_grade_track_code",
        "school_exam_plans",
        ["workspace_owner_id", "school_institute_id", "grade", "academic_track", "plan_code"],
    )
    op.drop_index("ix_school_exam_plans_pricing_period_id", "school_exam_plans")
    op.drop_constraint("fk_exam_plan_pricing_period", "school_exam_plans", type_="foreignkey")
    for column in ("is_current", "revision", "pricing_period_id"):
        op.drop_column("school_exam_plans", column)
    op.drop_table("school_exam_pricing_periods")
