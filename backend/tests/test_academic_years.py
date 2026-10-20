"""Synthetic records only: year history, re-registration and institute isolation."""

from backend.app.core.passwords import hash_password
from backend.app.db.database import SessionLocal
from backend.app.db.models import Role, User
from backend.tests.test_school_api import PASSWORD, login_headers, school_users
from fastapi.testclient import TestClient
from sqlalchemy import select

BASE = "/api/v1/school"


def student_data(**changes):
    return {
        "full_name": "Synthetic Student",
        "national_id": "0250155710",
        "birth_date": "2015-01-01",
        "grade": "GRADE_4",
        "academic_year": "1405/1406",
        "guardian_full_name": "Synthetic Guardian",
        "guardian_phone": "09120000000",
        "course_ids": [],
        "payments": [],
        **changes,
    }


def course(client, manager, year, grade="GRADE_4"):
    response = client.post(
        f"{BASE}/courses",
        headers=manager,
        json={"name": "Synthetic Class", "grade": grade, "price": "1000000", "academic_year": year},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_reenrollment_reuses_identity_preserves_paid_history_and_allows_same_grade(
    client: TestClient,
):
    manager, secretary = school_users(client)
    old = course(client, manager, "1405/1406")
    new = course(client, manager, "1406/1407", "GRADE_5")
    payload = student_data(
        course_ids=[old["id"]], payments=[{"method": "CASH", "amount": "1000000"}]
    )
    first = client.post(f"{BASE}/students/enroll", headers=secretary, json=payload)
    assert first.status_code == 201, first.text
    initial = first.json()
    initial = client.get(f"{BASE}/students/{initial['id']}", headers=manager).json()
    second = client.post(
        f"{BASE}/students/enroll",
        headers=secretary,
        json=student_data(
            academic_year="1406/1407",
            grade="GRADE_5",
            full_name="Must Not Replace Identity",
            course_ids=[new["id"]],
            registration_date="2026-10-20",
        ),
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == initial["id"]
    assert second.json()["full_name"] == initial["full_name"]
    history = second.json()["enrollments"]
    old_record = next(row for row in history if row["id"] == initial["enrollments"][0]["id"])
    assert old_record == initial["enrollments"][0]
    assert {(row["academic_year"], row["grade"]) for row in history} == {
        ("1405/1406", "GRADE_4"),
        ("1406/1407", "GRADE_5"),
    }
    assert client.post(f"{BASE}/students/enroll", headers=manager, json=payload).status_code == 201
    listed = client.get(f"{BASE}/students", headers=secretary).json()
    assert len(listed) == 1 and len(listed[0]["enrollments"]) == 3
    lookup = client.get(
        f"{BASE}/student-lookup", headers=secretary, params={"national_id": payload["national_id"]}
    )
    assert lookup.status_code == 200 and lookup.json()["id"] == initial["id"]


def test_years_editable_dates_catalog_and_registration_validation(client: TestClient):
    manager, secretary = school_users(client)
    years = client.get(f"{BASE}/academic-years", headers=secretary).json()
    assert {row["name"] for row in years} == {"1405/1406", "1406/1407"}
    payload = {"name": "1407/1408", "starts_on": "2028-09-22", "ends_on": "2029-06-21"}
    assert client.post(f"{BASE}/academic-years", headers=secretary, json=payload).status_code == 403
    assert client.post(f"{BASE}/academic-years", headers=manager, json=payload).status_code == 201
    assert client.post(f"{BASE}/academic-years", headers=manager, json=payload).status_code == 409
    assert (
        client.patch(
            f"{BASE}/academic-years", headers=manager, json={**payload, "ends_on": "2029-07-01"}
        ).json()["ends_on"]
        == "2029-07-01"
    )
    assert (
        client.post(
            f"{BASE}/academic-years", headers=manager, json={**payload, "name": "1407/1410"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{BASE}/academic-years", headers=manager, json={**payload, "ends_on": "2020-01-01"}
        ).status_code
        == 422
    )
    old = course(client, manager, "1405/1406")
    # Same name/grade in another year is a separate class and price history.
    new = course(client, manager, "1406/1407")
    assert old["id"] != new["id"]
    invalid = client.post(
        f"{BASE}/students/enroll",
        headers=secretary,
        json=student_data(academic_year="1406/1407", course_ids=[old["id"]]),
    )
    assert invalid.status_code == 422
    assert (
        client.post(
            f"{BASE}/students/enroll",
            headers=secretary,
            json=student_data(academic_year="1409/1410"),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/courses",
            headers=manager,
            json={
                "name": "Unknown Year",
                "grade": "GRADE_4",
                "price": "1",
                "academic_year": "1409/1410",
            },
        ).status_code
        == 422
    )
    period = client.get(f"{BASE}/exam-pricing-periods", headers=manager).json()[0]
    exam = {
        "grade": "GRADE_4",
        "plan_code": "YEAR-TEST",
        "exam_count": 20,
        "exam_unit_price": "50000",
        "exam_total": "1000000",
        "book_voucher_amount": "0",
        "book_voucher_discount": "0",
        "pricing_period_id": period["id"],
        "academic_year": "1406/1407",
    }
    assert client.post(f"{BASE}/exam-plans", headers=manager, json=exam).status_code == 422
    new_period = client.post(
        f"{BASE}/exam-pricing-periods",
        headers=manager,
        json={"academic_year": "1406/1407", "name": period["name"], "starts_on": "2027-08-01"},
    )
    assert new_period.status_code == 201
    exam["pricing_period_id"] = new_period.json()["id"]
    plan = client.post(f"{BASE}/exam-plans", headers=manager, json=exam)
    assert plan.status_code == 201, plan.text
    assert (
        client.post(
            f"{BASE}/students/enroll",
            headers=secretary,
            json=student_data(exam_registered=True, exam_plan_id=plan.json()["id"]),
        ).status_code
        == 422
    )
    accepted = client.post(
        f"{BASE}/students/enroll",
        headers=secretary,
        json=student_data(
            academic_year="1406/1407", exam_registered=True, exam_plan_id=plan.json()["id"]
        ),
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["enrollments"][0]["total_amount"] == "1000000.00"


def test_class_changes_use_enrollment_grade_and_year_not_original_student_grade(client: TestClient):
    manager, secretary = school_users(client)
    initial = client.post(f"{BASE}/students/enroll", headers=secretary, json=student_data()).json()
    old = course(client, manager, "1406/1407", "GRADE_5")
    future = client.post(
        f"{BASE}/students/enroll",
        headers=secretary,
        json=student_data(academic_year="1406/1407", grade="GRADE_5", course_ids=[old["id"]]),
    ).json()
    assert future["id"] == initial["id"] and future["grade"] == "GRADE_4"
    enrollment = next(row for row in future["enrollments"] if row["academic_year"] == "1406/1407")
    target = client.post(
        f"{BASE}/courses",
        headers=manager,
        json={
            "name": "Replacement Teacher",
            "grade": "GRADE_5",
            "academic_year": "1406/1407",
            "price": "1500000",
        },
    ).json()
    base = f"{BASE}/students/{future['id']}/enrollments/{enrollment['id']}/classes"
    changed = client.patch(
        f"{base}/{old['id']}",
        headers=secretary,
        json={
            "new_course_id": target["id"],
            "reason": "Synthetic future-year teacher change",
            "expected_old_price": "1000000",
            "expected_new_price": "1500000",
            "expected_total": "1000000",
        },
    )
    assert changed.status_code == 200, changed.text
    wrong_year = course(client, manager, "1405/1406", "GRADE_5")
    rejected = client.patch(
        f"{base}/{target['id']}",
        headers=manager,
        json={
            "new_course_id": wrong_year["id"],
            "reason": "Wrong year must be rejected",
            "expected_old_price": "1500000",
            "expected_new_price": "1000000",
            "expected_total": "1500000",
        },
    )
    assert rejected.status_code == 422


def test_two_secretaries_and_unrelated_manager_cannot_cross_year_or_student_scope(
    client: TestClient,
):
    manager, first = school_users(client)
    record = client.post(f"{BASE}/students/enroll", headers=first, json=student_data()).json()
    second_school = client.post(
        f"{BASE}/institutes", headers=manager, json={"name": "Synthetic Second"}
    ).json()
    assert (
        client.post(
            f"{BASE}/institutes/{second_school['id']}/secretaries",
            headers=manager,
            json={
                "first_name": "Second",
                "last_name": "Secretary",
                "email": "year.second@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 201
    )
    second = login_headers(client, "year.second@example.com")
    with SessionLocal.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        session.add(
            User(
                email="year.outsider@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="Unrelated",
                last_name="Manager",
                business_category="EDUCATION",
                roles=[role],
            )
        )
    outsider = login_headers(client, "year.outsider@example.com")
    for actor in (second, outsider):
        assert (
            client.get(
                f"{BASE}/student-lookup", headers=actor, params={"national_id": "0250155710"}
            ).json()
            is None
        )
        assert client.get(f"{BASE}/students/{record['id']}", headers=actor).status_code == 404
    custom = {"name": "1407/1408", "starts_on": "2028-09-22", "ends_on": "2029-06-21"}
    assert client.post(f"{BASE}/academic-years", headers=manager, json=custom).status_code == 201
    assert "1407/1408" not in {
        y["name"] for y in client.get(f"{BASE}/academic-years", headers=second).json()
    }
    assert "1407/1408" not in {
        y["name"] for y in client.get(f"{BASE}/academic-years", headers=outsider).json()
    }
    assert client.patch(f"{BASE}/academic-years", headers=outsider, json=custom).status_code == 422
    assert (
        client.post(
            f"{BASE}/students/enroll", headers=second, json=student_data(academic_year="1407/1408")
        ).status_code
        == 422
    )
