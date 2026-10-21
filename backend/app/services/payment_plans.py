"""Server-authoritative, exact Toman splits and automatic Persian-month schedules."""

from datetime import date
from decimal import Decimal

from backend.app.core.persian_calendar import add_persian_months
from backend.app.schemas.payment_plan import PaymentPart, PaymentPlanCreate


def build_payment_plan(total: Decimal, plan: PaymentPlanCreate, anchor: date) -> list[PaymentPart]:
    if total < 0 or not total.is_finite() or total != total.quantize(Decimal("0.01")):
        raise ValueError("مبلغ کل پرداخت معتبر نیست.")
    rows = list(plan.items)
    if len(plan.check_details) > plan.installment_count:
        raise ValueError("تعداد اطلاعات چک از تعداد اقساط بیشتر است.")
    for row in rows:
        if row.method == "INSTALLMENT":
            raise ValueError("اقساط فقط توسط سامانه محاسبه می‌شوند؛ تعداد اقساط را انتخاب کنید.")
        if row.method == "CHECK" and row.due_date is None:
            raise ValueError("برای هر چک تاریخ سررسید را انتخاب کنید.")
    assigned = sum((row.amount for row in rows), Decimal("0"))
    remaining = total - assigned
    if remaining < 0:
        raise ValueError("جمع بخش‌های پرداخت نمی‌تواند بیشتر از مبلغ فاکتور باشد.")
    if plan.installment_count:
        cents = int(remaining * 100)
        if cents < plan.installment_count:
            raise ValueError("مانده برای تعداد اقساط انتخاب‌شده کافی نیست.")
        base, remainder = divmod(cents, plan.installment_count)
        for i in range(plan.installment_count):
            detail = plan.check_details[i] if i < len(plan.check_details) else None
            rows.append(
                PaymentPart(
                    amount=Decimal(base + (1 if i < remainder else 0)) / 100,
                    method=plan.installment_method,
                    due_date=(
                        detail.due_date if detail and plan.installment_method == "CHECK" else None
                    )
                    or add_persian_months(anchor, i + 1),
                    tracking_code=detail.tracking_code
                    if detail and plan.installment_method == "CHECK"
                    else None,
                    sayad_id=detail.sayad_id
                    if detail and plan.installment_method == "CHECK"
                    else None,
                )
            )
    elif remaining != 0:
        raise ValueError("برنامه پرداخت باید کل فاکتور را پوشش دهد؛ برای مانده اقساط انتخاب کنید.")
    if len(rows) > 120:
        raise ValueError("تعداد بخش‌های پرداخت بیش از حد مجاز است.")
    return rows
