import os
import re
import subprocess
import sys
from decimal import Decimal
from unittest.mock import patch

from backend.app.core.passwords import hash_password
from backend.app.db.database import SessionLocal, engine
from backend.app.db.models import Role, SchoolExamPlan, User
from backend.tests.test_school_api import PASSWORD, login_headers, school_users
from fastapi.testclient import TestClient
from scripts.security_check import Response, csp_issues, fetch, sensitive_response
from scripts.security_routes import PUBLIC, inventory
from sqlalchemy import delete, event, select


def test_all_api_routes_enforce_authentication_before_handling(client: TestClient) -> None:
    routes = inventory()
    assert len(routes) > 50
    for route in routes:
        method, path = str(route["method"]), str(route["path"])
        if (method, path) in PUBLIC:
            continue
        assert route["authenticated"], (method, path)
        concrete = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000001", path)
        response = client.request(method, concrete)
        assert response.status_code == 401, (method, path, response.status_code)


def test_school_get_requests_do_not_seed_or_write(client: TestClient) -> None:
    manager, employee = school_users(client)
    # Deliberately missing catalog: reading must not silently reinstall it.
    with SessionLocal.begin() as session:
        session.execute(delete(SchoolExamPlan))
    writes = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|DROP)\b", statement, re.IGNORECASE):
            writes.append(statement.split()[0])

    event.listen(engine, "before_cursor_execute", capture)
    try:
        for actor in (manager, employee):
            for path in (
                "institutes",
                "courses",
                "students",
                "exam-plans",
                "exam-pricing-periods",
                "registration-fees",
                "special-supports",
            ):
                assert client.get(f"/api/v1/school/{path}", headers=actor).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert writes == []


def test_cookie_or_cross_origin_form_cannot_authenticate(client: TestClient) -> None:
    _, employee = school_users(client)
    token = employee["Authorization"].split()[1]
    response = client.post(
        "/api/v1/school/students/enroll",
        headers={"Origin": "https://untrusted.invalid", "Cookie": f"access_token={token}"},
        data={"full_name": "Cross origin"},
    )
    assert response.status_code == 401
    preflight = client.options(
        "/api/v1/school/students/enroll",
        headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_scanner_distinguishes_spa_from_exposed_files() -> None:
    assert not sensitive_response(Response(200, {}, b"<!doctype html><div id='root'></div>"))
    assert sensitive_response(Response(200, {}, b"JWT_SECRET=example-private-value"))
    assert sensitive_response(Response(200, {}, b'{"version":3,"sources":[]}'))
    assert not sensitive_response(Response(404, {}, b"Not found"))
    assert csp_issues("frame-ancestors 'none'")
    assert not csp_issues(
        "default-src 'self'; script-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )


def test_scanner_never_follows_redirects() -> None:
    from scripts.security_check import NoRedirect

    assert NoRedirect().redirect_request(None, None, 302, "", {}, "http://other.invalid") is None
    with patch("scripts.security_check.build_opener") as opener:
        response = opener.return_value.open.return_value
        response.status, response.headers = 200, {}
        response.read.return_value = b""
        assert fetch("http://localhost/").status == 200
        response.read.assert_called_once_with(1_048_576)


def test_school_isolation_blocks_direct_ids_reads_and_payment_writes(client: TestClient) -> None:
    manager, first_secretary = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={
            "name": "کلاس خصوصی",
            "grade": "GRADE_7",
            "price": "1000",
        },
    ).json()
    registration = {
        "full_name": "دانش‌آموز خصوصی",
        "national_id": "9712345678",
        "birth_date": "2013-01-01",
        "grade": "GRADE_7",
        "guardian_full_name": "ولی",
        "guardian_phone": "09120000000",
        "course_ids": [course["id"]],
        "payments": [{"method": "INSTALLMENT", "amount": "1000", "due_date": "2030-01-01"}],
    }
    enrolled = client.post(
        "/api/v1/school/students/enroll", headers=first_secretary, json=registration
    )
    assert enrolled.status_code == 201
    student = enrolled.json()
    payment = student["enrollments"][0]["payments"][0]
    school = client.post(
        "/api/v1/school/institutes", headers=manager, json={"name": "مدرسه جداگانه"}
    ).json()
    created = client.post(
        f"/api/v1/school/institutes/{school['id']}/secretaries",
        headers=manager,
        json={
            "first_name": "Other",
            "last_name": "Secretary",
            "email": "isolated@example.com",
            "password": PASSWORD,
        },
    )
    assert created.status_code == 201
    second_secretary = login_headers(client, "isolated@example.com")
    assert (
        client.patch(
            "/api/v1/school/institutes/active",
            headers=manager,
            json={"school_institute_id": school["id"]},
        ).status_code
        == 200
    )
    with SessionLocal.begin() as session:
        role = session.scalar(select(Role).where(Role.name == "MANAGER"))
        session.add(
            User(
                email="isolated.manager@example.com",
                password_hash=hash_password(PASSWORD),
                first_name="Other",
                last_name="Manager",
                business_category="EDUCATION",
                roles=[role],
            )
        )
    outsider = login_headers(client, "isolated.manager@example.com")
    for actor in (second_secretary, manager, outsider):
        assert (
            client.get(f"/api/v1/school/students/{student['id']}", headers=actor).status_code == 404
        )
        assert client.get("/api/v1/school/students", headers=actor).json() == []
        response = client.patch(
            f"/api/v1/school/payments/{payment['id']}", headers=actor, json={"status": "PAID"}
        )
        assert response.status_code in {404, 422}
        response = client.post(
            "/api/v1/school/students/enroll",
            headers=actor,
            json=registration | {"national_id": "9712345679"},
        )
        assert response.status_code == 422
    # Rejected requests made no cross-institute payment or enrollment change.
    unchanged = client.get(f"/api/v1/school/students/{student['id']}", headers=first_secretary)
    assert Decimal(unchanged.json()["enrollments"][0]["amount_paid"]) == 0
    assert len(client.get("/api/v1/school/students", headers=first_secretary).json()) == 1
    own_users = client.get("/api/v1/users", headers=manager).json()
    assert "isolated.manager@example.com" not in {row["email"] for row in own_users}


def test_manager_secretary_password_reset_has_its_own_throttle(client: TestClient) -> None:
    manager, _ = school_users(client)
    school = client.get("/api/v1/school/institutes", headers=manager).json()[0]
    secretary = client.get(
        f"/api/v1/school/institutes/{school['id']}/secretaries",
        headers=manager,
    ).json()[0]
    path = f"/api/v1/school/institutes/{school['id']}/secretaries/{secretary['id']}/password"
    for _ in range(client.app.state.settings.AUTH_RATE_LIMIT_ATTEMPTS):
        assert client.patch(path, headers=manager, json={"password": PASSWORD}).status_code == 204
    blocked = client.patch(path, headers=manager, json={"password": PASSWORD})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    # Login attempts use a separate action namespace, not the password-reset bucket.
    assert login_headers(client, "manager@example.com")


def test_unit_suite_refuses_an_external_database() -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+psycopg://invalid.invalid/not_a_real_database"
    result = subprocess.run(
        [sys.executable, "-c", "import backend.tests.conftest"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "refusing to create/drop tables in an external database" in result.stderr
