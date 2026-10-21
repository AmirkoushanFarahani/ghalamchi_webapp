"""Persist mixed/scheduled cost payments; preserve existing paid-cost semantics."""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20261021_0033"
down_revision = "20261021_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_school_costs_valid_school_cost_payment_method"), "school_costs", type_="check"
    )
    op.create_check_constraint(
        "valid_school_cost_payment_method",
        "school_costs",
        "payment_method IN ('CASH','CHECK','BANK_TRANSFER','INSTALLMENT','MIXED')",
    )
    table = op.create_table(
        "school_cost_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "cost_id",
            sa.Uuid(),
            sa.ForeignKey("school_costs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recorded_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("tracking_code", sa.String(100), nullable=True),
        sa.Column("sayad_id", sa.String(32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="positive_cost_payment_amount"),
        sa.CheckConstraint(
            "status IN ('PAID','CANCELLED') OR method NOT IN ('CHECK','INSTALLMENT') "
            "OR due_date IS NOT NULL",
            name="scheduled_cost_payment_due_date",
        ),
        sa.CheckConstraint(
            "method IN ('CASH','BANK_TRANSFER','CHECK','INSTALLMENT')",
            name="valid_cost_payment_method",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','PAID','BOUNCED','CANCELLED')", name="valid_cost_payment_status"
        ),
    )
    op.create_index("ix_school_cost_payments_cost_id", "school_cost_payments", ["cost_id"])
    op.create_index("ix_school_cost_payments_due_date", "school_cost_payments", ["due_date"])
    # Old costs (including checks) were already treated as paid. Preserve history.
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id, created_by_id, amount, payment_method, check_due_date, "
                "cost_date, tracking_code FROM school_costs"
            )
        )
        .mappings()
    )
    for row in rows:
        op.get_bind().execute(
            table.insert().values(
                id=uuid4(),
                cost_id=row["id"],
                recorded_by_id=row["created_by_id"],
                amount=row["amount"],
                method=row["payment_method"],
                status="PAID",
                due_date=row["check_due_date"],
                paid_on=row["cost_date"],
                tracking_code=row["tracking_code"],
            )
        )


def downgrade() -> None:
    raise RuntimeError(
        "Mixed payment history requires reviewed rollback, not destructive flattening"
    )
