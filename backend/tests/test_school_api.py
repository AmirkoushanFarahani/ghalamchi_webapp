from datetime import date
from decimal import Decimal

from backend.app.core.passwords import hash_password
from backend.app.db.database import SessionLocal
from backend.app.db.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy import select

PASSWORD = "school-demo-password-123"


def login_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def school_users(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    with SessionLocal.begin() as session:
        manager_role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        employee_role = session.scalar(select(Role).where(Role.name == "EMPLOYEE"))
        assert manager_role is not None and employee_role is not None
        manager = User(
            email="manager@example.com",
            password_hash=hash_password(PASSWORD),
            first_name="School",
            last_name="Manager",
            business_category="EDUCATION",
            roles=[manager_role],
        )
        session.add(manager)
        session.flush()
        session.add(
            User(
                email="employee@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="School",
                last_name="Employee",
                business_category="EDUCATION",
                school_manager_id=manager.id,
                roles=[employee_role],
            )
        )
    return (
        login_headers(client, "manager@example.com"),
        login_headers(client, "employee@example.com"),
    )


def test_manager_courses_employee_enrollment_and_shared_student_view(client: TestClient) -> None:
    manager, employee = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "ریاضی تقویتی", "grade": "GRADE_7", "price": "1200000"},
    )
    assert course.status_code == 201
    assert client.post(
        "/api/v1/school/courses",
        headers=employee,
        json={"name": "مجاز نیست", "grade": "GRADE_7", "price": "1"},
    ).status_code == 403
    discount = client.post(
        "/api/v1/school/discounts",
        headers=manager,
        json={"code": "WELCOME10", "percentage": "10"},
    )
    assert discount.status_code == 201
    enrolled = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json={
            "full_name": "دانش‌آموز آزمایشی",
            "national_id": "1234567890",
            "birth_date": "2013-01-01",
            "grade": "GRADE_7",
            "guardian_full_name": "ولی آزمایشی",
            "guardian_phone": "09120000000",
            "course_ids": [course.json()["id"]],
            "discount_code": "welcome10",
            "payments": [
                {"amount": "200000", "method": "CASH"},
                {"amount": "500000", "method": "INSTALLMENT", "due_date": "2030-01-01"},
            ],
        },
    )
    assert enrolled.status_code == 201
    enrollment = enrolled.json()["enrollments"][0]
    assert enrollment["subtotal"] == "1200000.00"
    assert enrollment["discount_amount"] == "120000.00"
    assert enrollment["total_amount"] == "1080000.00"
    assert enrollment["amount_paid"] == "200000"
    assert enrollment["status"] == "PARTIALLY_PAID"
    students = client.get("/api/v1/school/students", headers=manager).json()
    assert students[0]["full_name"] == enrolled.json()["full_name"]
    installment = next(item for item in enrollment["payments"] if item["method"] == "INSTALLMENT")
    cleared = client.patch(
        f"/api/v1/school/payments/{installment['id']}", headers=employee, json={"status": "PAID"}
    )
    assert cleared.status_code == 200


def test_second_institute_has_a_separate_secretary_and_student_data(client: TestClient) -> None:
    manager, employee = school_users(client)
    first_school = client.get("/api/v1/school/institutes", headers=manager)
    assert first_school.status_code == 200
    assert len(first_school.json()) == 1
    second = client.post("/api/v1/school/institutes", headers=manager, json={"name": "شعبه دوم"})
    assert second.status_code == 201
    secretary = client.post(
        f"/api/v1/school/institutes/{second.json()['id']}/secretaries",
        headers=manager,
        json={"first_name": "Second", "last_name": "Secretary", "email": "second@example.com", "password": PASSWORD},
    )
    assert secretary.status_code == 201
    second_headers = login_headers(client, "second@example.com")
    assert client.get("/api/v1/school/students", headers=second_headers).json() == []

    course = client.post("/api/v1/school/courses", headers=manager, json={"name": "کلاس اول", "grade": "GRADE_7", "price": "1"})
    assert course.status_code == 201
    enrolled = client.post("/api/v1/school/students/enroll", headers=employee, json={
        "full_name": "دانش‌آموز شعبه اول", "national_id": "9999999999", "birth_date": "2013-01-01", "grade": "GRADE_7",
        "guardian_full_name": "ولی", "guardian_phone": "09120000000", "course_ids": [course.json()["id"]],
    })
    assert enrolled.status_code == 201
    assert client.get("/api/v1/school/students", headers=second_headers).json() == []
    comparison = client.get("/api/v1/school/institutes/comparison", headers=manager)
    assert comparison.status_code == 200
    assert {row["school_name"] for row in comparison.json()} == {"آموزشگاه اول", "شعبه دوم"}


def test_employee_cannot_choose_course_from_another_grade(client: TestClient) -> None:
    manager, employee = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "علوم", "grade": "GRADE_8", "price": "100000"},
    ).json()
    response = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json={
            "full_name": "دانش‌آموز دوم",
            "national_id": "1234567891",
            "birth_date": str(date(2014, 1, 1)),
            "grade": "GRADE_7",
            "guardian_full_name": "ولی دوم",
            "guardian_phone": "09120000001",
            "course_ids": [course["id"]],
        },
    )
    assert response.status_code == 422


def test_only_manager_can_edit_course_details(client: TestClient) -> None:
    manager, employee = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "علوم", "grade": "GRADE_8", "price": "100000"},
    ).json()

    updated = client.patch(
        f"/api/v1/school/courses/{course['id']}",
        headers=manager,
        json={
            "name": "علوم پیشرفته",
            "instructor_name": "خانم احمدی",
            "grade": "GRADE_8",
            "price": "125000",
            "is_active": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "علوم پیشرفته"
    assert updated.json()["instructor_name"] == "خانم احمدی"
    assert Decimal(updated.json()["price"]) == Decimal("125000")
    assert updated.json()["is_active"] is False

    denied = client.patch(
        f"/api/v1/school/courses/{course['id']}",
        headers=employee,
        json={
            "name": "نباید تغییر کند",
            "grade": "GRADE_8",
            "price": "1",
            "is_active": True,
        },
    )
    assert denied.status_code == 403


def test_manager_registration_fees_are_added_to_optional_student_services(
    client: TestClient,
) -> None:
    manager, employee = school_users(client)
    updated = client.put(
        "/api/v1/school/registration-fees",
        headers=manager,
        json={"book_price": "3000", "exam_price": "2000"},
    )
    assert updated.status_code == 200
    assert Decimal(updated.json()["book_price"]) == Decimal("3000")
    assert Decimal(updated.json()["exam_price"]) == Decimal("2000")
    employee_fees = client.get("/api/v1/school/registration-fees", headers=employee)
    assert employee_fees.status_code == 200
    assert Decimal(employee_fees.json()["book_price"]) == Decimal("3000")
    assert Decimal(employee_fees.json()["exam_price"]) == Decimal("2000")
    exam_plans = client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=employee)
    assert exam_plans.status_code == 200
    plan = next(item for item in exam_plans.json() if item["plan_code"] == "0215")
    assert plan["exam_total"] == "10400000.00"
    assert plan["book_voucher_amount"] == "2000000.00"
    assert plan["book_voucher_discount"] == "300000.00"

    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "Optional class", "grade": "GRADE_7", "price": "1000"},
    )
    assert course.status_code == 201
    enrolled = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json={
            "full_name": "Student with optional services",
            "national_id": "1234567892",
            "birth_date": "2013-01-01",
            "grade": "GRADE_7",
            "guardian_full_name": "Guardian",
            "guardian_phone": "09120000002",
            "course_ids": [course.json()["id"]],
            "book_voucher_eligible": True,
            "exam_registered": True,
            "exam_plan_id": plan["id"],
            "payments": [
                {"amount": "3000", "method": "INSTALLMENT", "due_date": "2030-01-01"},
                {"amount": "3000", "method": "INSTALLMENT", "due_date": "2030-02-01"},
            ],
        },
    )
    assert enrolled.status_code == 201
    enrollment = enrolled.json()["enrollments"][0]
    assert enrollment["book_price"] == "1700000.00"
    assert enrollment["exam_price"] == "10400000.00"
    assert enrollment["subtotal"] == "12101000.00"
    assert enrollment["total_amount"] == "12101000.00"
    assert len(enrollment["payments"]) == 2

    no_class_enrollment = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json={
            "full_name": "Student without classes",
            "national_id": "1234567893",
            "birth_date": "2013-01-01",
            "grade": "GRADE_7",
            "guardian_full_name": "Guardian two",
            "guardian_phone": "09120000003",
            "course_ids": [],
        },
    )
    assert no_class_enrollment.status_code == 201
    no_class = no_class_enrollment.json()["enrollments"][0]
    assert Decimal(no_class["subtotal"]) == Decimal("0")
    assert no_class["courses"] == []


def test_only_manager_can_edit_exam_plan(client: TestClient) -> None:
    manager, employee = school_users(client)
    plans = client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=manager)
    assert plans.status_code == 200
    plan = plans.json()[0]

    updated = client.patch(
        f"/api/v1/school/exam-plans/{plan['id']}",
        headers=manager,
        json={
            "grade": "GRADE_7",
            "academic_track": None,
            "plan_code": plan["plan_code"],
            "exam_count": 30,
            "exam_unit_price": "500000",
            "exam_total": "15000000",
            "book_voucher_amount": "2500000",
            "book_voucher_discount": "400000",
            "is_active": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["exam_count"] == 30
    assert Decimal(updated.json()["exam_total"]) == Decimal("15000000")

    denied = client.patch(
        f"/api/v1/school/exam-plans/{plan['id']}",
        headers=employee,
        json={
            "grade": "GRADE_7",
            "academic_track": None,
            "plan_code": plan["plan_code"],
            "exam_count": 1,
            "exam_unit_price": "1",
            "exam_total": "1",
            "book_voucher_amount": "0",
            "book_voucher_discount": "0",
            "is_active": True,
        },
    )
    assert denied.status_code == 403


def test_only_manager_can_create_exam_plan(client: TestClient) -> None:
    manager, employee = school_users(client)
    body = {
        "grade": "GRADE_6",
        "academic_track": None,
        "plan_code": "CUSTOM-26",
        "exam_count": 20,
        "exam_unit_price": "400000",
        "exam_total": "8000000",
        "book_voucher_amount": "1500000",
        "book_voucher_discount": "200000",
        "is_active": True,
    }
    created = client.post("/api/v1/school/exam-plans", headers=manager, json=body)
    assert created.status_code == 201
    assert created.json()["plan_code"] == "CUSTOM-26"
    assert created.json()["grade"] == "GRADE_6"
    assert client.post("/api/v1/school/exam-plans", headers=employee, json=body).status_code == 403


def test_check_cost_requires_and_returns_a_due_date(client: TestClient) -> None:
    manager, _ = school_users(client)
    missing_date = client.post(
        "/api/v1/school/costs",
        headers=manager,
        json={
            "factor_number": "CHECK-COST-001",
            "reason": "Utility payment",
            "amount": "500000",
            "cost_date": "2030-01-01",
            "payment_method": "CHECK",
        },
    )
    assert missing_date.status_code == 422

    created = client.post(
        "/api/v1/school/costs",
        headers=manager,
        json={
            "factor_number": "CHECK-COST-001",
            "reason": "Utility payment",
            "amount": "500000",
            "cost_date": "2030-01-01",
            "payment_method": "CHECK",
            "check_due_date": "2030-02-01",
        },
    )
    assert created.status_code == 201
    assert created.json()["check_due_date"] == "2030-02-01"
