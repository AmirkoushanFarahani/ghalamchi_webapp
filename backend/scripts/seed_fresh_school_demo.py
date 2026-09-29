"""Create an isolated local school demo workspace with known credentials.

The script only creates the two accounts named below and their own sample data.
It does not delete or change any existing workspace.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.app.core.passwords import hash_password
from backend.app.db.bootstrap import seed_rbac
from backend.app.db.database import SessionLocal
from backend.app.db.models import (
    EnrollmentCourse,
    EnrollmentPayment,
    Role,
    SchoolCourse,
    Student,
    StudentEnrollment,
    User,
)

MANAGER_EMAIL = "demo.school.manager2@example.com"
SECRETARY_EMAIL = "demo.school.secretary2@example.com"
PASSWORD = "SchoolDemo#2026"


def main() -> None:
    with SessionLocal.begin() as session:
        seed_rbac(session)
        existing = session.scalars(
            select(User).where(User.email.in_((MANAGER_EMAIL, SECRETARY_EMAIL)))
        ).all()
        if existing:
            raise RuntimeError("The fresh school demo accounts already exist.")

        manager_role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        employee_role = session.scalar(select(Role).where(Role.name == "EMPLOYEE"))
        if manager_role is None or employee_role is None:
            raise RuntimeError("Required demo roles are missing.")

        manager = User(
            email=MANAGER_EMAIL,
            password_hash=hash_password(PASSWORD),
            first_name="مدیر",
            last_name="آموزشگاه آزمایشی جدید",
            business_category="EDUCATION",
            roles=[manager_role],
        )
        session.add(manager)
        session.flush()
        secretary = User(
            email=SECRETARY_EMAIL,
            password_hash=hash_password(PASSWORD),
            first_name="منشی",
            last_name="آموزشگاه آزمایشی جدید",
            business_category="EDUCATION",
            school_manager_id=manager.id,
            roles=[employee_role],
        )
        session.add(secretary)
        session.flush()

        courses = []
        for name, grade, price in (
            ("ریاضی هفتم", "GRADE_7", "2500000"),
            ("علوم هشتم", "GRADE_8", "2800000"),
            ("آمادگی آزمون نهم", "GRADE_9", "3200000"),
            ("فیزیک دهم", "GRADE_10", "3600000"),
            ("شیمی یازدهم", "GRADE_11", "3900000"),
            ("جمع‌بندی دوازدهم", "GRADE_12", "4500000"),
        ):
            course = SchoolCourse(
                workspace_owner_id=manager.id,
                name=name,
                grade=grade,
                price=Decimal(price),
            )
            session.add(course)
            courses.append(course)
        session.flush()

        today = date.today()
        samples = (
            ("مریم رضایی", "9100000001", "GRADE_7", courses[0], "PAID", "2500000", "2500000"),
            ("علی احمدی", "9100000002", "GRADE_8", courses[1], "UNPAID", "2800000", "0"),
            ("سارا محمدی", "9100000003", "GRADE_9", courses[2], "PARTIALLY_PAID", "3200000", "1200000"),
            ("امیر حسینی", "9100000004", "GRADE_10", courses[3], "UNPAID", "3600000", "0"),
            ("نگار کریمی", "9100000005", "GRADE_11", courses[4], "PAID", "3900000", "3900000"),
            ("رضا موسوی", "9100000006", "GRADE_12", courses[5], "PARTIALLY_PAID", "4500000", "1500000"),
        )
        for index, (name, national_id, grade, course, status, total, paid) in enumerate(samples):
            student = Student(
                workspace_owner_id=manager.id,
                created_by_id=secretary.id,
                full_name=name,
                national_id=national_id,
                birth_date=date(2010 + index % 4, 5, 10),
                registration_date=today - timedelta(days=index * 2),
                grade=grade,
                guardian_full_name=f"ولی {name}",
                guardian_phone=f"0912000100{index + 1}",
                student_phone=f"0912000200{index + 1}",
            )
            session.add(student)
            session.flush()
            total_amount = Decimal(total)
            paid_amount = Decimal(paid)
            enrollment = StudentEnrollment(
                workspace_owner_id=manager.id,
                student_id=student.id,
                created_by_id=secretary.id,
                subtotal=total_amount,
                discount_amount=Decimal("0"),
                book_price=Decimal("0"),
                exam_price=Decimal("0"),
                total_amount=total_amount,
                amount_paid=paid_amount,
                balance_due=total_amount - paid_amount,
                status=status,
            )
            session.add(enrollment)
            session.flush()
            session.add(
                EnrollmentCourse(
                    enrollment_id=enrollment.id,
                    course_id=course.id,
                    course_name=course.name,
                    price=course.price,
                )
            )
            if paid_amount:
                session.add(
                    EnrollmentPayment(
                        workspace_owner_id=manager.id,
                        enrollment_id=enrollment.id,
                        recorded_by_id=secretary.id,
                        amount=paid_amount,
                        method="CASH",
                        status="PAID",
                    )
                )
            if total_amount > paid_amount:
                session.add(
                    EnrollmentPayment(
                        workspace_owner_id=manager.id,
                        enrollment_id=enrollment.id,
                        recorded_by_id=secretary.id,
                        amount=total_amount - paid_amount,
                        method="INSTALLMENT" if index % 2 else "CHECK",
                        due_date=today - timedelta(days=3) if index == 1 else today + timedelta(days=12),
                        tracking_code=f"DEMO-NEW-{index + 1:02d}",
                        status="PENDING",
                    )
                )
    print("Fresh school demo workspace created.")


if __name__ == "__main__":
    main()
