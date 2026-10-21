"""Synthetic PostgreSQL lock test; refuses the actual application database.

Run only against a disposable `azari_mixed_test_*` database, migrated to head.
The operator drops that explicitly named test database afterward. Never logs records.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from backend.app.db.database import SessionLocal, engine
from backend.app.db.models import Role, SchoolAcademicYear, SchoolInstitute, User
from backend.app.schemas.payment_plan import PaymentPlanCreate, PaymentPlanReplace
from backend.app.schemas.school import CourseCreate, SchoolCostCreate, StudentEnrollmentCreate
from backend.app.services.school import SchoolConflictError, SchoolService
from sqlalchemy import select


def main() -> None:
    if engine.dialect.name != "postgresql" or not (engine.url.database or "").startswith(
        "azari_mixed_test_"
    ):
        raise RuntimeError("Only disposable azari_mixed_test_* PostgreSQL databases are allowed")
    plan = PaymentPlanCreate(installment_count=3)
    with SessionLocal() as session:
        role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        assert role is not None
        actor = User(
            email=f"synthetic-{uuid4()}@example.invalid",
            password_hash="disabled-synthetic",
            first_name="Synthetic",
            last_name="Concurrency",
            business_category="EDUCATION",
            roles=[role],
        )
        session.add(actor)
        session.flush()
        institute = SchoolInstitute(manager_id=actor.id, name="Synthetic concurrency only")
        session.add(institute)
        session.flush()
        actor.active_school_institute_id = institute.id
        session.add(
            SchoolAcademicYear(
                workspace_owner_id=actor.id,
                school_institute_id=institute.id,
                name="1405/1406",
                starts_on=date(2026, 9, 23),
                ends_on=date(2027, 6, 21),
            )
        )
        session.commit()
        actor_id = actor.id
        service = SchoolService(session, actor)
        course = service.create_course(
            CourseCreate(name="Synthetic", grade="GRADE_7", price=Decimal("1000"))
        )
        student = service.create_enrollment(
            StudentEnrollmentCreate(
                full_name="Synthetic Student",
                national_id="SYNTHETIC-ONLY",
                birth_date="2013-01-01",
                grade="GRADE_7",
                guardian_full_name="Synthetic Guardian",
                guardian_phone="09120000000",
                course_ids=[course.id],
                payment_plan=plan,
            )
        )
        enrollment = student.enrollments[0]
        student_id, enrollment_id = student.id, enrollment.id
        student_replace = PaymentPlanReplace(
            expected_balance=enrollment.balance_due,
            expected_pending_ids=[p.id for p in enrollment.payments],
            plan=PaymentPlanCreate(items=[{"amount": "1000", "method": "CASH"}]),
        )
        cost = service.create_cost(
            SchoolCostCreate(
                reason="Synthetic",
                amount=Decimal("1000"),
                cost_date="2026-10-21",
                payment_plan=plan,
            )
        )
        cost_id = cost.id
        cost_replace = PaymentPlanReplace(
            expected_balance=cost.balance_due,
            expected_pending_ids=[p.id for p in cost.payments],
            plan=PaymentPlanCreate(items=[{"amount": "1000", "method": "CASH"}]),
        )

    def race(kind: str) -> None:
        barrier = Barrier(2)

        def replace_once(_: int) -> str:
            with SessionLocal() as session:
                actor = session.get(User, actor_id)
                assert actor is not None
                service = SchoolService(session, actor)
                barrier.wait(timeout=15)
                try:
                    if kind == "student":
                        service.replace_enrollment_plan(student_id, enrollment_id, student_replace)
                    else:
                        service.replace_cost_plan(cost_id, cost_replace)
                    return "saved"
                except SchoolConflictError:
                    session.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(replace_once, range(2))) == ["conflict", "saved"]

    race("student")
    race("cost")
    print(
        "PASS PostgreSQL concurrent student and cost replacements: "
        "one saved, one stale conflict; no duplicate receipt"
    )


if __name__ == "__main__":
    main()
