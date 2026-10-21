"""Idempotent installation of the dated catalog extracted from examsheet.xlsx."""

import json
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.currency import from_rials
from backend.app.db.models import ExamPricingPeriod, SchoolExamPlan, SchoolInstitute
from backend.app.services.academic_years import ensure_initial_years


def install_exam_catalog(session: Session, owner_id: UUID, school_id: UUID) -> int:
    """Append missing workbook prices. Never alter existing plans or registrations."""
    session.scalar(select(SchoolInstitute).where(SchoolInstitute.id == school_id).with_for_update())
    ensure_initial_years(session, owner_id, school_id)
    catalog = json.loads(
        Path(__file__).with_name("exam_pricing_catalog.json").read_text(encoding="utf-8")
    )
    existing_periods = {
        period.name: period
        for period in session.scalars(
            select(ExamPricingPeriod).where(
                ExamPricingPeriod.school_institute_id == school_id,
                ExamPricingPeriod.academic_year == "1405/1406",
            )
        )
    }
    existing_plans = {
        (plan.pricing_period_id, plan.grade, plan.academic_track, plan.plan_code)
        for plan in session.scalars(
            select(SchoolExamPlan).where(
                SchoolExamPlan.school_institute_id == school_id,
                SchoolExamPlan.academic_year == "1405/1406",
            )
        )
    }
    added = 0
    for index, source in enumerate(catalog["periods"]):
        period = existing_periods.get(source["name"])
        starts_on = date.fromisoformat(source["starts_on"]) if source["starts_on"] else None
        ends_on = date.fromisoformat(source["ends_on"]) if source["ends_on"] else None
        if period is not None and (period.starts_on, period.ends_on) != (starts_on, ends_on):
            raise ValueError("An existing period has the workbook name but different dates")
        if period is None:
            period = ExamPricingPeriod(
                workspace_owner_id=owner_id,
                school_institute_id=school_id,
                name=source["name"],
                starts_on=starts_on,
                ends_on=ends_on,
            )
            session.add(period)
            session.flush()
            existing_periods[period.name] = period
        for row in catalog["rows"]:
            key = (period.id, row["grade"], row["academic_track"], source["plan_code"])
            if key in existing_plans:
                continue
            count, unit, total = row["prices"][index]
            session.add(
                SchoolExamPlan(
                    workspace_owner_id=owner_id,
                    school_institute_id=school_id,
                    pricing_period_id=period.id,
                    grade=row["grade"],
                    academic_track=row["academic_track"],
                    plan_code=source["plan_code"],
                    exam_count=count,
                    exam_unit_price=from_rials(unit),
                    exam_total=from_rials(total),
                    book_voucher_amount=from_rials(row["book_voucher_amount"]),
                    book_voucher_discount=from_rials(row["book_voucher_discount"]),
                )
            )
            existing_plans.add(key)
            added += 1
    session.flush()
    return added
