"""All persisted business amounts and public API money values use Toman.

Only explicitly identified legacy workbook/snapshot/model boundaries use Rial.
Never apply this conversion to normal API inputs or already converted DB values.
"""

from decimal import Decimal

CURRENCY = "TOMAN"
CURRENCY_LABEL = "تومان"
RIALS_PER_TOMAN = Decimal("10")
AUDIT_AMOUNT_KEYS = {
    "amount",
    "price",
    "old_price",
    "new_price",
    "old_total",
    "new_total",
    "refund_amount",
    "subtotal",
    "total_amount",
    "attendance_charge",
    "cancellation_fee",
    "retained_amount",
}


def from_rials(value: Decimal | str | int | float) -> Decimal:
    converted = Decimal(str(value)) / RIALS_PER_TOMAN
    if not converted.is_finite() or converted != converted.quantize(Decimal("0.01")):
        raise ValueError("Rial source amount cannot be represented exactly in Toman")
    return converted.quantize(Decimal("0.01"))
