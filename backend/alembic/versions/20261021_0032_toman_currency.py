"""Convert all existing monetary records from Rial to Toman exactly once.

Run online with all application writers stopped. Alembic's transactional revision
marker is the one-time conversion marker. Counts, quantities, rates and IDs stay
unchanged. No rounding is allowed; an unrepresentable value aborts the transaction.
"""

from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision = "20261021_0032"
down_revision = "20261020_0031"
branch_labels = None
depends_on = None

# Frozen migration inventory, not runtime ORM metadata (future columns must not
# accidentally be converted when an old database runs this migration).
MONEY_COLUMNS = {
    "products": ("unit_price",),
    "journal_lines": ("debit", "credit"),
    "invoices": ("subtotal", "tax", "total", "amount_paid"),
    "invoice_items": ("unit_price", "tax", "line_subtotal", "line_total"),
    "invoice_checks": ("amount",),
    "payments": ("amount",),
    "payment_allocations": ("amount",),
    "bills": ("subtotal", "tax", "total", "amount_paid"),
    "bill_items": ("unit_price", "tax", "line_subtotal", "line_total"),
    "bill_payments": ("amount",),
    "bill_payment_allocations": ("amount",),
    "expenses": ("amount",),
    "school_courses": ("price",),
    "school_registration_fees": ("book_price", "exam_price"),
    "school_exam_plans": (
        "exam_unit_price",
        "exam_total",
        "book_voucher_amount",
        "book_voucher_discount",
    ),
    "school_special_supports": ("monthly_price", "seasonal_price"),
    "student_enrollments": (
        "subtotal",
        "discount_amount",
        "book_price",
        "exam_price",
        "special_support_price",
        "book_voucher_discount",
        "total_amount",
        "amount_paid",
        "balance_due",
    ),
    "enrollment_courses": ("price",),
    "enrollment_payments": ("amount",),
    "enrollment_class_changes": (
        "old_price",
        "new_price",
        "old_total",
        "new_total",
        "refund_amount",
    ),
    "enrollment_service_cancellations": (
        "original_price",
        "attendance_charge",
        "cancellation_fee",
        "retained_amount",
        "old_total",
        "new_total",
        "refund_amount",
    ),
    "enrollment_support_changes": ("old_price", "new_price", "old_total", "new_total"),
    "school_costs": ("amount",),
}
AUDIT_MONEY_KEYS = {name for names in MONEY_COLUMNS.values() for name in names}


def exact_toman(value: object) -> Decimal:
    amount = Decimal(str(value)) / Decimal("10")
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError(
            "Currency conversion requires explicit precision review; no data converted"
        )
    return amount.quantize(Decimal("0.01"))


def convert_audit_metadata(value: object) -> object:
    if isinstance(value, list):
        return [convert_audit_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in AUDIT_MONEY_KEYS and item is not None and not isinstance(item, bool):
            try:
                result[key] = str(exact_toman(item))
            except InvalidOperation:
                result[key] = item  # Free-form text is not a monetary value.
        else:
            result[key] = convert_audit_metadata(item)
    if result != value:
        result["currency"] = "TOMAN"
    return result


def convert_existing_money(connection: Connection) -> None:
    tables = {
        name: sa.table(name, *(sa.column(c, sa.Numeric(18, 2)) for c in columns))
        for name, columns in MONEY_COLUMNS.items()
    }
    # Preflight ALL values before changing any table. Existing 0.01 Rial values
    # would require 0.001 Toman, which the current financial precision cannot store.
    for table in tables.values():
        for row in connection.execute(sa.select(table)).yield_per(1000):
            for value in row:
                if value is not None:
                    exact_toman(value)
    for table in tables.values():
        connection.execute(table.update().values({c.name: c / Decimal("10") for c in table.c}))

    audit = sa.table("audit_events", sa.column("id", sa.Uuid()), sa.column("metadata", sa.JSON()))
    for row in connection.execute(sa.select(audit)).mappings().all():
        converted = convert_audit_metadata(row["metadata"])
        if converted != row["metadata"]:
            connection.execute(
                audit.update().where(audit.c.id == row["id"]).values(metadata=converted)
            )

    predictions = sa.table(
        "ml_predictions",
        sa.column("id", sa.Uuid()),
        sa.column("pipeline", sa.String()),
        sa.column("predicted_value", sa.JSON()),
    )
    for row in (
        connection.execute(
            sa.select(predictions).where(predictions.c.pipeline == "cash_flow_forecast")
        )
        .mappings()
        .all()
    ):
        value = dict(row["predicted_value"])
        if value.get("currency") == "TOMAN":
            continue
        value["points"] = [
            {
                **point,
                **{
                    key: float(Decimal(str(point[key])) / 10)
                    for key in ("predicted", "lower", "upper")
                    if key in point
                },
            }
            for point in value.get("points", [])
        ]
        # Feedback is historical free text: preserve it and record its original unit.
        value["legacy_feedback_currency"] = "IRR"
        value["currency"] = "TOMAN"
        connection.execute(
            predictions.update().where(predictions.c.id == row["id"]).values(predicted_value=value)
        )


def upgrade() -> None:
    convert_existing_money(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Restore the pre-conversion backup; automatic currency downgrade is unsafe")
