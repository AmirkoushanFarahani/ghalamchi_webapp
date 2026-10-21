"""Synthetic-only student corrections: both staff roles, immutable enrollment history."""

import pytest
from backend.app.core.passwords import hash_password
from backend.app.db.database import SessionLocal
from backend.app.db.models import Role, User
from backend.tests.test_mixed_payments import enroll
from backend.tests.test_school_api import PASSWORD, login_headers, school_users
from sqlalchemy import select


def personal(student):
    keys = (
        "full_name",
        "national_id",
        "birth_date",
        "grade",
        "academic_track",
        "student_phone",
        "guardian_full_name",
        "guardian_phone",
        "mother_full_name",
        "mother_phone",
        "address",
        "previous_school",
        "emergency_contact",
        "notes",
    )
    return {key: student.get(key) for key in keys}


@pytest.mark.parametrize("role", ["manager", "secretary"])
def test_staff_edit_personal_details_and_grade_not_year_or_financial_history(client, role):
    manager, secretary = school_users(client)
    student, enrollment, registration = enroll(client, manager, secretary)
    url = f"/api/v1/school/students/{student['id']}"
    student = client.get(url, headers=manager).json()
    update = {
        **personal(student),
        "full_name": "Updated Synthetic Student",
        "grade": "GRADE_8",
        "national_id": "9876543210",
        "guardian_full_name": "Synthetic Father",
        "mother_full_name": "Synthetic Mother",
        "mother_phone": "09120000001",
        "academic_track": "should disappear",
        "notes": "multi word note\nsecond line",
    }
    auth = manager if role == "manager" else secretary
    response = client.patch(url, headers=auth, json=update)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["grade"] == "GRADE_8"
    assert updated["academic_track"] is None
    assert updated["mother_full_name"] == "Synthetic Mother"
    assert updated["enrollments"] == student["enrollments"]
    assert client.get(url, headers=secretary).json()["national_id"] == "9876543210"
    assert (
        client.patch(url, headers=auth, json={**update, "academic_year": "1406/1407"}).status_code
        == 422
    )
    assert (
        client.patch(
            url, headers=auth, json={**update, "workspace_owner_id": student["id"]}
        ).status_code
        == 422
    )
    assert client.patch(url, json=update).status_code == 401
    # Optional mother fields can be cleared without changing father's information.
    clear = client.patch(
        url, headers=auth, json={**update, "mother_full_name": None, "mother_phone": None}
    )
    assert clear.status_code == 200
    assert clear.json()["mother_phone"] is None
    registration["national_id"] = "1111111111"
    other = client.post("/api/v1/school/students/enroll", headers=secretary, json=registration)
    assert other.status_code == 201
    assert (
        client.patch(url, headers=auth, json={**update, "national_id": "1111111111"}).status_code
        == 409
    )
    assert client.get(url, headers=auth).json()["national_id"] == "9876543210"


def test_mother_details_saved_on_first_registration_and_optional_on_others(client):
    manager, secretary = school_users(client)
    _, _, registration = enroll(client, manager, secretary)
    registration.update(
        national_id="5555555555", mother_full_name="Synthetic Mother", mother_phone="09120000002"
    )
    created = client.post("/api/v1/school/students/enroll", headers=secretary, json=registration)
    assert created.status_code == 201
    assert created.json()["mother_phone"] == "09120000002"
    found = client.get("/api/v1/school/student-lookup?national_id=5555555555", headers=secretary)
    assert found.json()["mother_full_name"] == "Synthetic Mother"


def test_student_edit_rejects_other_institute_secretary_and_unrelated_manager(client):
    manager, secretary = school_users(client)
    student, _, _ = enroll(client, manager, secretary)
    url = f"/api/v1/school/students/{student['id']}"
    second = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "Synthetic Second"}
    ).json()
    assert (
        client.post(
            f"/api/v1/school/institutes/{second['id']}/secretaries",
            headers=manager,
            json={
                "first_name": "Synthetic",
                "last_name": "Second",
                "email": "second.edit@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 201
    )
    other_secretary = login_headers(client, "second.edit@example.com")
    assert client.get(url, headers=other_secretary).status_code == 404
    assert client.patch(url, headers=other_secretary, json=personal(student)).status_code == 404
    client.patch(
        "/api/v1/school/institutes/active",
        headers=manager,
        json={"school_institute_id": second["id"]},
    )
    assert client.patch(url, headers=manager, json=personal(student)).status_code == 404
    with SessionLocal.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        session.add(
            User(
                email="outsider.edit@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="Synthetic",
                last_name="Outsider",
                business_category="EDUCATION",
                roles=[role],
            )
        )
    outsider = login_headers(client, "outsider.edit@example.com")
    assert client.get(url, headers=outsider).status_code == 404
    assert client.patch(url, headers=outsider, json=personal(student)).status_code == 404
