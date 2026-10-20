from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditEvent
from backend.tests.test_school_api import school_users
from fastapi.testclient import TestClient
from sqlalchemy import select


def course(
    client: TestClient, manager: dict[str, str], name: str, price: str, grade: str = "GRADE_10"
) -> dict:
    response = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": name, "instructor_name": name + " teacher", "grade": grade, "price": price},
    )
    assert response.status_code == 201
    return response.json()


def enroll(
    client: TestClient,
    employee: dict[str, str],
    courses: list[dict],
    paid: str = "1000",
    extra: dict | None = None,
) -> dict:
    response = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json={
            "full_name": "دانش‌آموز تغییر کلاس",
            "national_id": "9800000001",
            "birth_date": "2010-01-01",
            "grade": "GRADE_10",
            "guardian_full_name": "ولی دانش‌آموز",
            "guardian_phone": "09120000000",
            "course_ids": [c["id"] for c in courses],
            "payments": [{"amount": paid, "method": "CASH"}],
            **(extra or {}),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def change_url(student: dict, old: dict) -> str:
    base = f"/api/v1/school/students/{student['id']}/enrollments/{student['enrollments'][0]['id']}"
    return f"{base}/classes/{old['id']}"


def payload(student: dict, old: dict, new: dict, **extra: object) -> dict:
    return {
        "new_course_id": new["id"],
        "expected_old_price": old["price"],
        "expected_new_price": new["price"],
        "expected_total": student["enrollments"][0]["total_amount"],
        "reason": "درخواست تغییر دبیر",
        **extra,
    }


@pytest.mark.parametrize("actor", ["manager", "employee"])
@pytest.mark.parametrize("collect", [False, True])
def test_more_expensive_class_requires_difference_and_retains_history(
    client: TestClient, actor: str, collect: bool
) -> None:
    manager, employee = school_users(client)
    old = course(client, manager, "Physics Ahmadi", "1000")
    target = course(client, manager, "Physics Rezaei", "1500")
    student = enroll(client, employee, [old])
    reason = "درخواست دانش‌آموز برای تغییر دبیر\nبه دلیل تغییر برنامه هفتگی کلاس‌ها"
    data = payload(student, old, target, reason=reason)
    if collect:
        data["payment"] = {"amount": "500", "method": "BANK_TRANSFER", "tracking_code": "DIFF-1"}
    response = client.patch(
        change_url(student, old), headers=manager if actor == "manager" else employee, json=data
    )
    assert response.status_code == 200, response.text
    updated = response.json()["enrollments"][0]
    assert Decimal(updated["total_amount"]) == 1500
    assert Decimal(updated["amount_paid"]) == (1500 if collect else 1000)
    assert Decimal(updated["balance_due"]) == (0 if collect else 500)
    assert updated["courses"][0]["instructor_name"] == "Physics Rezaei teacher"
    assert updated["class_changes"][0]["old_instructor_name"] == "Physics Ahmadi teacher"
    assert updated["class_changes"][0]["reason"] == reason
    assert len(updated["payments"]) == (2 if collect else 1)
    assert client.patch(change_url(student, old), headers=employee, json=data).status_code == 422
    if not collect:
        pay_url = f"/api/v1/school/students/{student['id']}/enrollments/{updated['id']}/payments"
        paid = client.post(pay_url, headers=employee, json={"amount": "500", "method": "CASH"})
        assert paid.status_code == 201
        assert paid.json()["enrollments"][0]["status"] == "PAID"
        assert (
            client.post(
                pay_url, headers=employee, json={"amount": "500", "method": "CASH"}
            ).status_code
            == 422
        )
    with SessionLocal() as session:
        assert (
            session.scalar(select(AuditEvent).where(AuditEvent.action == "school.class.changed"))
            is not None
        )


@pytest.mark.parametrize("action", ["CREDIT", "PAY", "KEEP_CREDIT"])
def test_cheaper_class_credit_or_manager_refund(client: TestClient, action: str) -> None:
    manager, employee = school_users(client)
    old = course(client, manager, "Original", "1000")
    target = course(client, manager, "Cheaper", "700")
    student = enroll(client, employee, [old])
    response = client.patch(
        change_url(student, old),
        headers=employee,
        json=payload(
            student, old, target, excess_handling="CREDIT" if action == "CREDIT" else "REFUND"
        ),
    )
    assert response.status_code == 200, response.text
    updated = response.json()["enrollments"][0]
    assert Decimal(updated["credit_balance"]) == 300
    assert Decimal(updated["balance_due"]) == 0
    assert updated["status"] == "PAID"
    if action != "CREDIT":
        change = updated["class_changes"][0]
        base = f"/api/v1/school/students/{student['id']}/enrollments/{updated['id']}"
        url = f"{base}/refunds/{change['id']}"
        details = {
            "action": action,
            "method": "BANK_TRANSFER",
            "paid_on": date.today().isoformat(),
            "tracking_code": "REFUND-1",
        }
        assert client.patch(url, headers=employee, json=details).status_code == 403
        assert client.patch(url, headers=manager, json={"action": "PAY"}).status_code == 422
        result = client.patch(url, headers=manager, json=details)
        assert result.status_code == 200, result.text
        updated = result.json()["enrollments"][0]
        assert Decimal(updated["credit_balance"]) == (0 if action == "PAY" else 300)
        assert Decimal(updated["amount_paid"]) == (700 if action == "PAY" else 1000)
        assert len(updated["payments"]) == 1  # Original receipt remains immutable.
        assert client.patch(url, headers=manager, json=details).status_code == 409
        comparison = client.get("/api/v1/school/institutes/comparison", headers=manager).json()[0]
        assert Decimal(comparison["received_tuition"]) == Decimal(updated["amount_paid"])


def test_class_change_rejects_invalid_grade_duplicate_inactive_stale_and_cross_school(
    client: TestClient,
) -> None:
    manager, employee = school_users(client)
    old = course(client, manager, "Original", "1000")
    same_price = course(client, manager, "Equal price", "1000")
    wrong_grade = course(client, manager, "Other grade", "1500", "GRADE_11")
    inactive = course(client, manager, "Inactive", "1500")
    client.patch(
        f"/api/v1/school/courses/{inactive['id']}",
        headers=manager,
        json={
            **{k: inactive[k] for k in ("name", "grade", "price", "instructor_name")},
            "is_active": False,
        },
    )
    student = enroll(client, employee, [old, same_price])
    url = change_url(student, old)
    assert (
        client.patch(url, headers=employee, json=payload(student, old, wrong_grade)).status_code
        == 422
    )
    assert (
        client.patch(url, headers=employee, json=payload(student, old, inactive)).status_code == 422
    )
    assert (
        client.patch(url, headers=employee, json=payload(student, old, same_price)).status_code
        == 409
    )
    alternative = course(client, manager, "Alternative", "1700")
    assert (
        client.patch(
            url, headers=employee, json=payload(student, old, alternative, expected_new_price="1")
        ).status_code
        == 409
    )
    assert (
        client.patch(
            url,
            headers=employee,
            json=payload(student, old, alternative, payment={"amount": "1", "method": "CASH"}),
        ).status_code
        == 422
    )
    second = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "Another school"}
    ).json()
    client.patch(
        "/api/v1/school/institutes/active",
        headers=manager,
        json={"school_institute_id": second["id"]},
    )
    foreign = course(client, manager, "Foreign", "2000")
    assert (
        client.patch(url, headers=employee, json=payload(student, old, foreign)).status_code == 422
    )
    assert (
        client.patch(url, headers=manager, json=payload(student, old, alternative)).status_code
        == 422
    )
    assert (
        client.patch(
            url.replace(student["id"], str(uuid4())),
            headers=employee,
            json=payload(student, old, alternative),
        ).status_code
        == 422
    )
    unchanged = client.get(f"/api/v1/school/students/{student['id']}", headers=employee).json()[
        "enrollments"
    ][0]
    assert not unchanged["class_changes"]
    assert Decimal(unchanged["total_amount"]) == 2000


def test_discount_snapshot_addons_and_scheduled_difference(client: TestClient) -> None:
    manager, employee = school_users(client)
    old = course(client, manager, "Original", "1000")
    target = course(client, manager, "Other subject same grade", "1400")
    client.post(
        "/api/v1/school/discounts", headers=manager, json={"code": "TEN", "percentage": "10"}
    )
    student = enroll(client, employee, [old], paid="900", extra={"discount_code": "TEN"})
    response = client.patch(
        change_url(student, old),
        headers=employee,
        json=payload(
            student,
            old,
            target,
            payment={"amount": "400", "method": "CHECK", "due_date": "2030-01-01"},
        ),
    )
    assert response.status_code == 200, response.text
    updated = response.json()["enrollments"][0]
    assert Decimal(updated["discount_amount"]) == 100
    assert Decimal(updated["total_amount"]) == 1300
    assert Decimal(updated["balance_due"]) == 400
    check = next(p for p in updated["payments"] if p["method"] == "CHECK")
    url = f"/api/v1/school/payments/{check['id']}"
    assert client.patch(url, headers=employee, json={"status": "CANCELLED"}).status_code == 200
    assert client.patch(url, headers=employee, json={"status": "PAID"}).status_code == 409
    add_url = f"/api/v1/school/students/{student['id']}/enrollments/{updated['id']}/payments"
    assert (
        client.post(
            add_url, headers=employee, json={"amount": "400", "method": "CHECK"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            add_url, headers=employee, json={"amount": "400", "method": "BANK_TRANSFER"}
        ).status_code
        == 201
    )


def test_service_cancellation_uses_attended_session_count_and_ten_percent_fee(
    client: TestClient,
) -> None:
    manager, employee = school_users(client)
    response = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={
            "name": "طرح فیزیک بیست جلسه‌ای",
            "instructor_name": "آقای احمدی",
            "grade": "GRADE_10",
            "price": "10000000",
            "session_count": 20,
        },
    )
    assert response.status_code == 201, response.text
    service = response.json()
    student = enroll(client, employee, [service], paid="10000000")
    enrollment = student["enrollments"][0]
    base = f"/api/v1/school/students/{student['id']}/enrollments/{enrollment['id']}"
    cancelled = client.post(
        f"{base}/cancellations",
        headers=employee,
        json={
            "service_type": "COURSE",
            "course_id": service["id"],
            "expected_original_price": "10000000",
            "expected_total": "10000000",
            "attended_sessions": 3,
            "reason": "انصراف دانش‌آموز",
            "excess_handling": "REFUND",
        },
    )
    assert cancelled.status_code == 201, cancelled.text
    updated = cancelled.json()["enrollments"][0]
    # 3/20 of 10,000,000 = 1,500,000, plus the 10% fee = 1,000,000.
    cancellation = updated["service_cancellations"][0]
    assert Decimal(cancellation["attendance_charge"]) == 1_500_000
    assert Decimal(cancellation["cancellation_fee"]) == 1_000_000
    assert Decimal(cancellation["retained_amount"]) == 2_500_000
    assert Decimal(cancellation["refund_amount"]) == 7_500_000
    assert cancellation["refund_status"] == "PENDING"
    assert Decimal(updated["total_amount"]) == 2_500_000
    assert Decimal(updated["credit_balance"]) == 7_500_000
    assert updated["courses"][0]["status"] == "CANCELLED"
    denied = client.patch(
        f"{base}/cancellations/{cancellation['id']}/refund",
        headers=employee,
        json={"action": "PAY", "method": "CASH", "paid_on": date.today().isoformat()},
    )
    assert denied.status_code == 403
    completed = client.patch(
        f"{base}/cancellations/{cancellation['id']}/refund",
        headers=manager,
        json={
            "action": "PAY",
            "method": "BANK_TRANSFER",
            "paid_on": date.today().isoformat(),
            "tracking_code": "REFUND-EXAMPLE",
        },
    )
    assert completed.status_code == 200, completed.text
    assert Decimal(completed.json()["enrollments"][0]["amount_paid"]) == 2_500_000


@pytest.mark.parametrize("actor", ["manager", "employee"])
def test_manager_or_secretary_can_change_student_special_support(
    client: TestClient, actor: str
) -> None:
    manager, employee = school_users(client)
    original_support = client.post(
        "/api/v1/school/special-supports",
        headers=manager,
        json={"name": "پشتیبان الف", "monthly_price": "100", "seasonal_price": "250"},
    )
    replacement_support = client.post(
        "/api/v1/school/special-supports",
        headers=manager,
        json={"name": "پشتیبان ب", "monthly_price": "300", "seasonal_price": "700"},
    )
    assert original_support.status_code == replacement_support.status_code == 201
    course_record = course(client, manager, "کلاس فیزیک", "1000")
    student = enroll(
        client,
        employee,
        [course_record],
        paid="1100",
        extra={
            "special_support": {
                "support_id": original_support.json()["id"],
                "period": "MONTHLY",
            }
        },
    )
    enrollment = student["enrollments"][0]
    url = (
        f"/api/v1/school/students/{student['id']}/enrollments/"
        f"{enrollment['id']}/special-support"
    )
    result = client.patch(
        url,
        headers=manager if actor == "manager" else employee,
        json={
            "support_id": replacement_support.json()["id"],
            "period": "MONTHLY",
            "expected_old_price": "100",
            "expected_total": "1100",
            "reason": "درخواست دانش‌آموز",
        },
    )
    assert result.status_code == 200, result.text
    updated = result.json()["enrollments"][0]
    assert updated["special_support_name"] == "پشتیبان ب"
    assert Decimal(updated["special_support_price"]) == 300
    assert Decimal(updated["total_amount"]) == 1300
    assert Decimal(updated["amount_paid"]) == 1100
    assert Decimal(updated["balance_due"]) == 200
    assert updated["support_changes"][0]["old_name"] == "پشتیبان الف"
    assert updated["support_changes"][0]["new_name"] == "پشتیبان ب"
    stale = client.patch(
        url,
        headers=employee,
        json={
            "support_id": original_support.json()["id"],
            "period": "MONTHLY",
            "expected_old_price": "100",
            "expected_total": "1100",
            "reason": "درخواست تکراری",
        },
    )
    assert stale.status_code == 409
