"""Populate the manager's second school with isolated, realistic demo data.

The manager-controlled catalog is copied from ``آموزشگاه اول`` to ``دخترونه``.
Student, enrollment, payment, and cost records are created only for ``دخترونه``.
The script is intentionally idempotent: it stops rather than duplicating students.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.app.db.database import SessionLocal
from backend.app.db.models import (
    DiscountCode,
    EnrollmentCourse,
    EnrollmentPayment,
    SchoolCost,
    SchoolCourse,
    SchoolExamPlan,
    SchoolInstitute,
    SchoolRegistrationFees,
    SchoolSpecialSupport,
    Student,
    StudentEnrollment,
    User,
)


MANAGER_EMAIL = "demo.school.manager2@example.com"
SOURCE_SCHOOL_NAME = "آموزشگاه اول"
TARGET_SCHOOL_NAME = "دخترونه"


def copy_catalog(session, manager: User, source: SchoolInstitute, target: SchoolInstitute) -> None:
    """Copy manager configured items, retaining their values but changing scope."""
    for course in session.scalars(select(SchoolCourse).where(SchoolCourse.school_institute_id == source.id)):
        session.add(SchoolCourse(
            workspace_owner_id=manager.id, school_institute_id=target.id,
            name=course.name, instructor_name=course.instructor_name,
            grade=course.grade, price=course.price, is_active=course.is_active,
        ))
    for discount in session.scalars(select(DiscountCode).where(DiscountCode.school_institute_id == source.id)):
        session.add(DiscountCode(
            workspace_owner_id=manager.id, school_institute_id=target.id,
            code=discount.code, percentage=discount.percentage,
            expires_on=discount.expires_on, max_uses=discount.max_uses,
            uses_count=0, is_active=discount.is_active,
        ))
    source_fees = session.scalar(select(SchoolRegistrationFees).where(
        SchoolRegistrationFees.school_institute_id == source.id
    ))
    if source_fees is not None:
        session.add(SchoolRegistrationFees(
            workspace_owner_id=manager.id, school_institute_id=target.id,
            book_price=source_fees.book_price, exam_price=source_fees.exam_price,
        ))
    for plan in session.scalars(select(SchoolExamPlan).where(SchoolExamPlan.school_institute_id == source.id)):
        session.add(SchoolExamPlan(
            workspace_owner_id=manager.id, school_institute_id=target.id,
            grade=plan.grade, academic_track=plan.academic_track, plan_code=plan.plan_code,
            exam_count=plan.exam_count, exam_unit_price=plan.exam_unit_price,
            exam_total=plan.exam_total, book_voucher_amount=plan.book_voucher_amount,
            book_voucher_discount=plan.book_voucher_discount, is_active=plan.is_active,
        ))
    for support in session.scalars(select(SchoolSpecialSupport).where(
        SchoolSpecialSupport.school_institute_id == source.id
    )):
        session.add(SchoolSpecialSupport(
            workspace_owner_id=manager.id, school_institute_id=target.id,
            name=support.name, monthly_price=support.monthly_price,
            seasonal_price=support.seasonal_price, is_active=support.is_active,
        ))
    session.flush()


def main() -> None:
    with SessionLocal.begin() as session:
        manager = session.scalar(select(User).where(User.email == MANAGER_EMAIL))
        if manager is None:
            raise RuntimeError("The school demo manager account was not found.")
        source = session.scalar(select(SchoolInstitute).where(
            SchoolInstitute.manager_id == manager.id, SchoolInstitute.name == SOURCE_SCHOOL_NAME
        ))
        target = session.scalar(select(SchoolInstitute).where(
            SchoolInstitute.manager_id == manager.id, SchoolInstitute.name == TARGET_SCHOOL_NAME
        ))
        if source is None or target is None:
            raise RuntimeError("Both schools must exist before creating the second-school demo.")
        if session.scalar(select(Student.id).where(Student.school_institute_id == target.id).limit(1)):
            print("Second-school demo data already exists; no records were duplicated.")
            return

        copy_catalog(session, manager, source, target)
        courses_by_grade = {
            course.grade: course for course in session.scalars(select(SchoolCourse).where(
                SchoolCourse.school_institute_id == target.id, SchoolCourse.is_active.is_(True)
            ))
        }
        plans_by_grade = {
            plan.grade: plan for plan in session.scalars(select(SchoolExamPlan).where(
                SchoolExamPlan.school_institute_id == target.id, SchoolExamPlan.is_active.is_(True)
            ))
        }
        if not courses_by_grade:
            raise RuntimeError("The source school has no active courses to copy.")

        today = date.today()
        student_names = (
            "آوا اسدی", "کیانا کاظمی", "نرگس یوسفی", "رها رستمی", "هلیا توکلی",
            "مبینا صادقی", "ستایش اکبری", "یسنا مرادی", "ترانه رحیمی", "باران شریفی",
            "آیلین کریمی", "درسا محمودی", "نازنین حیدری", "مهسا موسوی", "روژان امینی",
            "سوگند جعفری", "هانیه قاسمی", "یگانه حسینی", "مریم زارعی", "نگین عباسی",
            "ریحانه نادری", "زهرا نوروزی", "سارا رضوانی", "فاطمه محمدی",
        )
        grades = ("GRADE_7", "GRADE_8", "GRADE_9", "GRADE_10", "GRADE_11", "GRADE_12")
        tracks = {"GRADE_10": "تجربی", "GRADE_11": "ریاضی فیزیک", "GRADE_12": "انسانی"}

        for index, name in enumerate(student_names):
            grade = grades[index % len(grades)]
            course = courses_by_grade.get(grade) or next(iter(courses_by_grade.values()))
            plan = plans_by_grade.get(grade)
            include_exam = plan is not None and index % 3 != 1
            include_book = plan is not None and index % 4 in (0, 2)
            course_price = Decimal(course.price)
            exam_price = Decimal(plan.exam_total) if include_exam and plan else Decimal("0")
            book_discount = Decimal(plan.book_voucher_discount) if include_book and plan else Decimal("0")
            book_price = (Decimal(plan.book_voucher_amount) - book_discount) if include_book and plan else Decimal("0")
            subtotal = course_price + exam_price + book_price
            payment_case = index % 4
            paid_amount = subtotal if payment_case == 0 else (subtotal / 2).quantize(Decimal("1")) if payment_case == 1 else Decimal("0")
            balance = subtotal - paid_amount
            status = "PAID" if balance == 0 else "PARTIALLY_PAID" if paid_amount else "OVERDUE" if index % 5 == 2 else "UNPAID"
            student = Student(
                workspace_owner_id=manager.id, school_institute_id=target.id, created_by_id=manager.id,
                full_name=name, national_id=f"920000{index + 1:04d}",
                student_phone=f"091355{index + 10:05d}", birth_date=date(2010 + index % 5, 2 + index % 8, 10),
                registration_date=today - timedelta(days=3 + index * 3),
                first_exam_date=today + timedelta(days=7 + index), grade=grade,
                academic_track=tracks.get(grade), book_voucher_eligible=include_book,
                exam_registered=include_exam, guardian_full_name=f"ولی {name}",
                guardian_phone=f"091366{index + 10:05d}", address="اصفهان، مرکز آموزشی دخترونه",
                previous_school="مدرسه نمونه", notes="داده آزمایشی مرکز دخترونه",
            )
            session.add(student)
            session.flush()
            enrollment = StudentEnrollment(
                workspace_owner_id=manager.id, school_institute_id=target.id, student_id=student.id,
                created_by_id=manager.id, exam_plan_id=plan.id if plan else None,
                subtotal=subtotal, discount_amount=Decimal("0"), book_price=book_price,
                exam_price=exam_price, exam_plan_code=plan.plan_code if include_exam and plan else None,
                book_voucher_discount=book_discount, total_amount=subtotal, amount_paid=paid_amount,
                balance_due=balance, status=status,
            )
            session.add(enrollment)
            session.flush()
            session.add(EnrollmentCourse(
                enrollment_id=enrollment.id, course_id=course.id, course_name=course.name, price=course.price
            ))
            if paid_amount:
                session.add(EnrollmentPayment(
                    workspace_owner_id=manager.id, school_institute_id=target.id, enrollment_id=enrollment.id,
                    recorded_by_id=manager.id, amount=paid_amount, method="BANK_TRANSFER" if index % 2 else "CASH",
                    tracking_code=f"GIRLS-PAID-{index + 1:03d}", status="PAID",
                ))
            if balance:
                pending_due = today - timedelta(days=2 + index % 5) if status == "OVERDUE" else today + timedelta(days=7 + index)
                session.add(EnrollmentPayment(
                    workspace_owner_id=manager.id, school_institute_id=target.id, enrollment_id=enrollment.id,
                    recorded_by_id=manager.id, amount=balance,
                    method="CHECK" if index % 2 else "INSTALLMENT", due_date=pending_due,
                    tracking_code=f"GIRLS-DUE-{index + 1:03d}", status="PENDING",
                ))

        costs = (
            ("GIRLS-COST-001", "شرکت برق", "هزینه برق ماهانه", "18500000", "BANK_TRANSFER"),
            ("GIRLS-COST-002", "فروشگاه آموزشی", "خرید لوازم آموزشی", "32750000", "CASH"),
            ("GIRLS-COST-003", "شرکت اینترنت", "هزینه اینترنت", "8900000", "BANK_TRANSFER"),
            ("GIRLS-COST-004", "تجهیزات مدرسه", "تعمیر تجهیزات کلاس", "24700000", "CHECK"),
            ("GIRLS-COST-005", "خدمات نظافت", "هزینه نظافت", "15600000", "CASH"),
            ("GIRLS-COST-006", "اجاره ملک", "اجاره ماهانه", "95000000", "BANK_TRANSFER"),
        )
        for index, (factor, vendor, reason, amount, method) in enumerate(costs):
            session.add(SchoolCost(
                workspace_owner_id=manager.id, school_institute_id=target.id, created_by_id=manager.id,
                factor_number=factor, vendor_name=vendor, reason=reason, amount=Decimal(amount),
                cost_date=today - timedelta(days=index * 9), payment_method=method,
                check_due_date=today + timedelta(days=14) if method == "CHECK" else None,
                tracking_code=f"GIRLS-COST-TRACK-{index + 1:03d}", notes="هزینه آزمایشی مرکز دخترونه",
            ))
    print("Second-school catalog and demo data created successfully.")


if __name__ == "__main__":
    main()
