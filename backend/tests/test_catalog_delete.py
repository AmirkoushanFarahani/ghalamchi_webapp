from uuid import uuid4

import pytest
from backend.tests.test_school_api import school_users
from fastapi.testclient import TestClient


@pytest.mark.parametrize("kind", ["courses", "special-supports", "exam-plans"])
def test_manager_can_remove_and_restore_used_catalog_items_without_changing_students(
    client: TestClient,
    kind: str,
) -> None:
    manager, employee = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={
            "name": "کلاس آزمایشی",
            "grade": "GRADE_7",
            "price": "1000",
        },
    ).json()
    support = client.post(
        "/api/v1/school/special-supports",
        headers=manager,
        json={
            "name": "پشتیبان آزمایشی",
            "monthly_price": "200",
            "seasonal_price": "500",
        },
    ).json()
    plan = next(
        p
        for p in client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=manager).json()
        if p["plan_code"] == "0718"
    )
    registration = {
        "full_name": "دانش‌آموز آزمایشی",
        "national_id": "9900000001",
        "birth_date": "2013-01-01",
        "grade": "GRADE_7",
        "guardian_full_name": "ولی",
        "guardian_phone": "09120000000",
        "course_ids": [course["id"]],
        "exam_registered": True,
        "exam_plan_id": plan["id"],
        "special_support": {"support_id": support["id"], "period": "MONTHLY"},
    }
    student = client.post("/api/v1/school/students/enroll", headers=employee, json=registration)
    assert student.status_code == 201, student.text
    before = client.get(
        f"/api/v1/school/students/{student.json()['id']}", headers=employee
    ).json()
    item = {"courses": course, "special-supports": support, "exam-plans": plan}[kind]
    url = f"/api/v1/school/catalog/{kind}/{item['id']}"
    listing = f"/api/v1/school/{kind}"
    assert client.delete(url, headers=employee).status_code == 403
    assert client.post(url + "/restore", headers=employee).status_code == 403
    assert client.get(listing + "?include_deleted=true", headers=employee).status_code == 403
    assert client.delete(url, headers=manager).status_code == 204
    assert not any(row["id"] == item["id"] for row in client.get(listing, headers=employee).json())
    archived = client.get(listing + "?include_deleted=true", headers=manager).json()
    assert next(row for row in archived if row["id"] == item["id"])["is_deleted"]
    unchanged = client.get(f"/api/v1/school/students/{before['id']}", headers=employee)
    assert unchanged.json() == before
    blocked = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json=registration | {"national_id": "9900000002"},
    )
    assert blocked.status_code == 422
    assert client.post(url + "/restore", headers=manager).status_code == 204
    assert any(row["id"] == item["id"] for row in client.get(listing, headers=employee).json())
    allowed = client.post(
        "/api/v1/school/students/enroll",
        headers=employee,
        json=registration | {"national_id": "9900000002"},
    )
    assert allowed.status_code == 201, allowed.text
    school = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "مدرسه دیگر"}
    ).json()
    client.patch(
        "/api/v1/school/institutes/active",
        headers=manager,
        json={"school_institute_id": school["id"]},
    )
    assert client.delete(url, headers=manager).status_code == 404
    assert client.post(url + "/restore", headers=manager).status_code == 404
    assert (
        client.delete(f"/api/v1/school/catalog/{kind}/{uuid4()}", headers=manager).status_code
        == 404
    )


def test_exam_removal_keeps_all_price_versions_and_does_not_reseed(client: TestClient) -> None:
    manager, _ = school_users(client)
    original = client.get("/api/v1/school/exam-plans?grade=GRADE_7", headers=manager).json()[0]
    body = {
        key: original[key]
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
    } | {"exam_total": "12345678"}
    revised = client.patch(
        f"/api/v1/school/exam-plans/{original['id']}", headers=manager, json=body
    ).json()
    assert revised["revision"] == 2
    url = f"/api/v1/school/catalog/exam-plans/{revised['id']}"
    assert client.delete(url, headers=manager).status_code == 204
    hidden_ids = {original["id"], revised["id"]}
    for _ in range(2):
        visible = client.get("/api/v1/school/exam-plans", headers=manager).json()
        assert not hidden_ids.intersection(row["id"] for row in visible)
    history = client.get("/api/v1/school/exam-plans?include_deleted=true", headers=manager).json()
    assert len([row for row in history if row["id"] in hidden_ids and row["is_deleted"]]) == 2
    assert client.post(url + "/restore", headers=manager).status_code == 204
    restored = client.get("/api/v1/school/exam-plans", headers=manager).json()
    assert hidden_ids.issubset(row["id"] for row in restored)
