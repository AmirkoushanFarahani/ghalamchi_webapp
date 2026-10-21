"""Exact mixed plans and synthetic school/institute read AND write isolation."""

from datetime import date
from decimal import Decimal

import pytest
from backend.app.core.passwords import hash_password
from backend.app.core.persian_calendar import add_persian_months, to_jalali
from backend.app.db.database import SessionLocal
from backend.app.db.models import Role, User
from backend.app.schemas.payment_plan import PaymentPlanCreate
from backend.app.services.payment_plans import build_payment_plan
from backend.tests.test_school_api import PASSWORD, login_headers, school_users
from sqlalchemy import select


def plan():
    return {
        "items": [
            {"amount": "200", "method": "CASH"},
            {"amount": "100", "method": "BANK_TRANSFER", "tracking_code": "SYNTHETIC"},
            {"amount": "200", "method": "CHECK", "due_date": "2026-12-01", "sayad_id": "123"},
        ],
        "installment_count": 3,
    }


def test_exact_split_and_anchored_persian_months():
    parts = build_payment_plan(
        Decimal("1000"), PaymentPlanCreate.model_validate(plan()), date(2026, 9, 22)
    )
    assert sum(p.amount for p in parts) == Decimal("1000")
    assert [p.amount for p in parts[3:]] == [
        Decimal("166.67"),
        Decimal("166.67"),
        Decimal("166.66"),
    ]
    assert [to_jalali(p.due_date) for p in parts[3:]] == [
        (1405, 7, 30),
        (1405, 8, 30),
        (1405, 9, 30),
    ]
    # Clamp the anchored day, not the previous installment's shorter month.
    anchor = date(2026, 3, 20)  # 1404/12/29
    assert to_jalali(add_persian_months(anchor, 1)) == (1405, 1, 29)
    assert to_jalali(add_persian_months(date(2025, 3, 20), 12)) == (1404, 12, 29)


def test_automatic_check_installments_need_no_optional_details():
    result = build_payment_plan(
        Decimal("1000"),
        PaymentPlanCreate(installment_count=3, installment_method="CHECK"),
        date(2026, 9, 22),
    )
    assert all(
        p.method == "CHECK" and p.sayad_id is None and p.tracking_code is None for p in result
    )
    assert all(p.due_date is not None for p in result)
    assert sum(p.amount for p in result) == Decimal("1000")
    with_details = PaymentPlanCreate.model_validate(
        {
            "installment_count": 2,
            "installment_method": "CHECK",
            "check_details": [{"sayad_id": "123", "due_date": "2030-01-01"}],
        }
    )
    result = build_payment_plan(Decimal("1000"), with_details, date(2026, 9, 22))
    assert result[0].due_date == date(2030, 1, 1)
    assert result[0].sayad_id == "123"
    assert to_jalali(result[1].due_date) == (1405, 8, 30)


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [{"amount": "999", "method": "CASH"}]},
        {"items": [{"amount": "1001", "method": "CASH"}]},
        {"items": [{"amount": "1000", "method": "CHECK"}]},
        {"items": [{"amount": "1000", "method": "INSTALLMENT", "due_date": "2030-01-01"}]},
        {"items": [{"amount": "1000", "method": "CASH"}], "installment_count": 1},
    ],
)
def test_incomplete_overpaid_or_manual_schedules_rejected(payload):
    with pytest.raises(ValueError):
        build_payment_plan(
            Decimal("1000"), PaymentPlanCreate.model_validate(payload), date(2026, 10, 21)
        )


def enroll(client, manager, secretary):
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "Mixed synthetic", "grade": "GRADE_7", "price": "1000"},
    ).json()
    data = {
        "full_name": "Synthetic Student",
        "national_id": "1234567890",
        "grade": "GRADE_7",
        "birth_date": "2013-01-01",
        "guardian_full_name": "Synthetic Guardian",
        "guardian_phone": "09120000000",
        "course_ids": [course["id"]],
        "registration_date": "2026-09-22",
        "payment_plan": plan(),
    }
    result = client.post("/api/v1/school/students/enroll", headers=secretary, json=data)
    assert result.status_code == 201, result.text
    student = result.json()
    return student, student["enrollments"][0], data


def replacement(enrollment):
    return {
        "expected_balance": enrollment["balance_due"],
        "expected_pending_ids": [
            p["id"] for p in enrollment["payments"] if p["status"] in ("PENDING", "BOUNCED")
        ],
        "plan": {"items": [{"amount": enrollment["balance_due"], "method": "CASH"}]},
    }


def test_mixed_registration_replace_and_received_immutability(client):
    manager, secretary = school_users(client)
    student, enrollment, data = enroll(client, manager, secretary)
    assert Decimal(enrollment["amount_paid"]) == 300
    assert Decimal(enrollment["balance_due"]) == 700
    assert len(enrollment["payments"]) == 6
    paid_ids = {p["id"] for p in enrollment["payments"] if p["status"] == "PAID"}
    url = f"/api/v1/school/students/{student['id']}/enrollments/{enrollment['id']}/payment-plan"
    invalid = replacement(enrollment)
    invalid["plan"] = {"items": [{"amount": "1", "method": "CASH"}]}
    assert client.put(url, headers=secretary, json=invalid).status_code == 422
    saved = client.put(url, headers=secretary, json=replacement(enrollment))
    assert saved.status_code == 200, saved.text
    updated = saved.json()["enrollments"][0]
    assert Decimal(updated["balance_due"]) == 0
    assert Decimal(updated["amount_paid"]) == 1000
    assert paid_ids <= {p["id"] for p in updated["payments"] if p["status"] == "PAID"}
    assert sum(p["status"] == "CANCELLED" for p in updated["payments"]) == 4
    assert client.put(url, headers=manager, json=replacement(enrollment)).status_code == 409
    assert (
        client.patch(
            f"/api/v1/school/payments/{next(iter(paid_ids))}",
            headers=secretary,
            json={"status": "CANCELLED"},
        ).status_code
        == 409
    )
    data["national_id"] = "1234567891"
    data["payment_plan"] = {"items": [{"amount": "999", "method": "CASH"}]}
    assert (
        client.post("/api/v1/school/students/enroll", headers=secretary, json=data).status_code
        == 422
    )
    assert len(client.get("/api/v1/school/students", headers=secretary).json()) == 1


def test_cost_split_settlement_and_totals(client):
    manager, secretary = school_users(client)
    response = client.post(
        "/api/v1/school/costs",
        headers=manager,
        json={
            "reason": "Synthetic utility",
            "amount": "1000",
            "cost_date": "2026-09-22",
            "payment_plan": plan(),
        },
    )
    assert response.status_code == 201, response.text
    cost = response.json()
    assert cost["payment_method"] == "MIXED"
    assert Decimal(cost["amount_paid"]) == 300
    assert Decimal(cost["balance_due"]) == 700
    check = next(p for p in cost["payments"] if p["method"] == "CHECK")
    url = f"/api/v1/school/costs/{cost['id']}/payments/{check['id']}"
    assert client.patch(url, headers=secretary, json={"status": "PAID"}).status_code == 403
    assert client.patch(url, headers=manager, json={"status": "PAID"}).status_code == 200
    assert client.patch(url, headers=manager, json={"status": "PAID"}).status_code == 409
    assert (
        client.put(
            f"/api/v1/school/costs/{cost['id']}/payment-plan",
            headers=manager,
            json=replacement(cost),
        ).status_code
        == 409
    )
    totals = client.get("/api/v1/school/costs", headers=manager).json()
    assert Decimal(totals["total"]) == 1000
    assert Decimal(totals["total_paid"]) == 500
    assert Decimal(totals["total_outstanding"]) == 500
    assert client.get("/api/v1/school/costs", headers=secretary).status_code == 403


def test_class_and_support_difference_gets_a_complete_new_plan(client):
    manager, secretary = school_users(client)
    student, enrollment, data = enroll(client, manager, secretary)
    target = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={"name": "More expensive", "grade": "GRADE_7", "price": "1500"},
    ).json()
    url = f"/api/v1/school/students/{student['id']}/enrollments/{enrollment['id']}"
    change = client.patch(
        f"{url}/classes/{data['course_ids'][0]}",
        headers=secretary,
        json={
            "new_course_id": target["id"],
            "expected_old_price": "1000",
            "expected_new_price": "1500",
            "expected_total": "1000",
            "reason": "Synthetic multi-word reason",
            "payment_plan": {
                "items": [{"amount": "200", "method": "CASH"}],
                "installment_count": 2,
            },
        },
    )
    assert change.status_code == 200, change.text
    changed = change.json()["enrollments"][0]
    assert Decimal(changed["amount_paid"]) == 500
    assert Decimal(changed["balance_due"]) == 1000
    assert (
        sum(
            Decimal(p["amount"])
            for p in changed["payments"]
            if p["status"] in ("PENDING", "BOUNCED")
        )
        == 1000
    )
    support = client.post(
        "/api/v1/school/special-supports",
        headers=manager,
        json={"name": "Synthetic support", "monthly_price": "100", "seasonal_price": "300"},
    ).json()
    response = client.patch(
        f"{url}/special-support",
        headers=secretary,
        json={
            "support_id": support["id"],
            "period": "MONTHLY",
            "expected_old_price": "0",
            "expected_total": "1500",
            "reason": "Synthetic support change",
            "payment_plan": {"installment_count": 2},
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()["enrollments"][0]
    assert Decimal(updated["balance_due"]) == 1100
    assert (
        sum(Decimal(p["amount"]) for p in updated["payments"] if p["status"] == "PENDING") == 1100
    )


def test_new_payment_writes_and_reads_are_institute_scoped(client):
    manager, secretary = school_users(client)
    student, enrollment, _ = enroll(client, manager, secretary)
    cost = client.post(
        "/api/v1/school/costs",
        headers=manager,
        json={
            "reason": "Synthetic",
            "amount": "1000",
            "cost_date": "2026-09-22",
            "payment_plan": plan(),
        },
    ).json()
    second = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "Second synthetic"}
    ).json()
    assert (
        client.post(
            f"/api/v1/school/institutes/{second['id']}/secretaries",
            headers=manager,
            json={
                "first_name": "Second",
                "last_name": "Synthetic",
                "email": "second@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 201
    )
    second_secretary = login_headers(client, "second@example.com")
    plan_url = (
        f"/api/v1/school/students/{student['id']}/enrollments/{enrollment['id']}/payment-plan"
    )
    assert client.get(
        f"/api/v1/school/students/{student['id']}", headers=second_secretary
    ).status_code in (404, 422)
    assert client.put(
        plan_url, headers=second_secretary, json=replacement(enrollment)
    ).status_code in (404, 422)
    assert (
        client.patch(
            "/api/v1/school/institutes/active",
            headers=manager,
            json={"school_institute_id": second["id"]},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/school/costs", headers=manager).json()["items"] == []
    assert client.put(
        f"/api/v1/school/costs/{cost['id']}/payment-plan", headers=manager, json=replacement(cost)
    ).status_code in (404, 422)
    assert client.put(plan_url, headers=manager, json=replacement(enrollment)).status_code in (
        404,
        422,
    )
    with SessionLocal.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        session.add(
            User(
                email="outsider.mixed@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="Synthetic",
                last_name="Outsider",
                business_category="EDUCATION",
                roles=[role],
            )
        )
    outsider = login_headers(client, "outsider.mixed@example.com")
    assert client.get("/api/v1/school/students", headers=outsider).json() == []
    assert client.put(plan_url, headers=outsider, json=replacement(enrollment)).status_code in (
        404,
        422,
    )
    assert client.put(
        f"/api/v1/school/costs/{cost['id']}/payment-plan", headers=outsider, json=replacement(cost)
    ).status_code in (404, 422)
