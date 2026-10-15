from decimal import Decimal

from backend.app.db.database import SessionLocal
from backend.app.db.models import SchoolInstitute
from backend.app.services.exam_pricing import install_exam_catalog
from backend.tests.test_school_api import school_users
from fastapi.testclient import TestClient
from sqlalchemy import select


def plan_body(plan: dict) -> dict:
    return {
        key: plan[key]
        for key in (
            "grade",
            "academic_track",
            "plan_code",
            "pricing_period_id",
            "exam_count",
            "exam_unit_price",
            "exam_total",
            "book_voucher_amount",
            "book_voucher_discount",
            "is_active",
        )
    } | {"expected_revision": plan["revision"]}


def test_workbook_dates_prices_and_repeat_import(client: TestClient) -> None:
    manager, employee = school_users(client)
    periods = client.get("/api/v1/school/exam-pricing-periods", headers=employee).json()
    plans = client.get("/api/v1/school/exam-plans", headers=manager).json()
    assert len(periods) == 11
    assert len(plans) == 407
    assert all(
        Decimal(plan["exam_unit_price"]) * plan["exam_count"] == Decimal(plan["exam_total"])
        for plan in plans
    )
    first = next(p for p in periods if "15 اردیبهشت" in p["name"])
    last = next(p for p in periods if "18 مهر" in p["name"])
    assert first["starts_on"] is None and first["ends_on"] == "2026-05-05"
    assert last["starts_on"] == "2026-10-10" and last["ends_on"] is None
    price = next(
        p
        for p in plans
        if p["pricing_period_id"] == last["id"]
        and p["grade"] == "GRADE_12"
        and p["academic_track"] == "EXPERIMENTAL"
    )
    assert price["exam_count"] == 25
    assert Decimal(price["exam_total"]) == 15_000_000
    with SessionLocal.begin() as session:
        school = session.scalar(select(SchoolInstitute))
        assert school is not None
        assert install_exam_catalog(session, school.manager_id, school.id) == 0
    assert len(client.get("/api/v1/school/exam-plans", headers=manager).json()) == 407


def test_revisions_keep_student_invoice_and_can_restore_old_price(client: TestClient) -> None:
    manager, employee = school_users(client)
    plans = client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=manager).json()
    original = next(p for p in plans if p["plan_code"] == "0718")
    registration = {
        "full_name": "دانش‌آموز آزمون",
        "national_id": "9800000091",
        "birth_date": "2013-01-01",
        "grade": "GRADE_7",
        "guardian_full_name": "ولی",
        "guardian_phone": "09120000000",
        "course_ids": [],
        "exam_registered": True,
        "exam_plan_id": original["id"],
        "payments": [{"amount": original["exam_total"], "method": "CASH"}],
    }
    enrolled = client.post("/api/v1/school/students/enroll", headers=employee, json=registration)
    assert enrolled.status_code == 201, enrolled.text
    original_invoice = enrolled.json()["enrollments"][0]
    url = f"/api/v1/school/exam-plans/{original['id']}"
    new_body = plan_body(original) | {"exam_total": "11000000"}
    assert client.patch(url, headers=employee, json=new_body).status_code == 403
    changed = client.patch(url, headers=manager, json=new_body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] != original["id"]
    assert changed.json()["revision"] == 2
    assert client.patch(url, headers=manager, json=new_body).status_code == 409
    history = client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=employee).json()
    archived = next(p for p in history if p["id"] == original["id"])
    assert not archived["is_current"]
    assert archived["exam_total"] == original["exam_total"]
    unchanged = client.get(
        f"/api/v1/school/students/{enrolled.json()['id']}", headers=employee
    ).json()
    assert unchanged["enrollments"][0]["total_amount"] == original_invoice["total_amount"]
    assert (
        client.post(
            "/api/v1/school/students/enroll",
            headers=employee,
            json=registration | {"national_id": "9800000092"},
        ).status_code
        == 422
    )
    restore_url = url + "/restore"
    assert client.post(restore_url, headers=employee).status_code == 403
    restored = client.post(restore_url, headers=manager)
    assert restored.status_code == 200, restored.text
    assert restored.json()["revision"] == 3
    assert restored.json()["exam_total"] == original["exam_total"]


def test_period_validation_duplicates_and_school_isolation(client: TestClient) -> None:
    manager, employee = school_users(client)
    base = "/api/v1/school/exam-pricing-periods"
    data = {"name": "قیمت زمستان", "starts_on": "2027-01-01", "ends_on": "2027-03-01"}
    assert client.post(base, headers=employee, json=data).status_code == 403
    assert (
        client.post(base, headers=manager, json=data | {"ends_on": "2026-01-01"}).status_code == 422
    )
    assert client.post(base, headers=manager, json={"name": "بدون تاریخ"}).status_code == 422
    created = client.post(base, headers=manager, json=data)
    assert created.status_code == 201
    assert client.post(base, headers=manager, json=data).status_code == 409
    plan = {
        "grade": "GRADE_7",
        "academic_track": None,
        "plan_code": "WINTER",
        "pricing_period_id": created.json()["id"],
        "exam_count": 10,
        "exam_unit_price": "100000",
        "exam_total": "1000000",
        "book_voucher_amount": "0",
        "book_voucher_discount": "0",
    }
    first = client.post("/api/v1/school/exam-plans", headers=manager, json=plan)
    assert first.status_code == 201
    assert client.post("/api/v1/school/exam-plans", headers=manager, json=plan).status_code == 409
    another_period = client.post(
        base,
        headers=manager,
        json=data | {"name": "تابستان", "starts_on": "2027-06-01", "ends_on": None},
    ).json()
    assert (
        client.post(
            "/api/v1/school/exam-plans",
            headers=manager,
            json=plan | {"pricing_period_id": another_period["id"]},
        ).status_code
        == 201
    )
    school2 = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "مدرسه دوم"}
    ).json()
    client.patch(
        "/api/v1/school/institutes/active",
        headers=manager,
        json={"school_institute_id": school2["id"]},
    )
    assert client.post("/api/v1/school/exam-plans", headers=manager, json=plan).status_code == 422
    assert (
        client.post(
            f"/api/v1/school/exam-plans/{first.json()['id']}/restore", headers=manager
        ).status_code
        == 422
    )
    assert all(p["id"] != created.json()["id"] for p in client.get(base, headers=manager).json())
