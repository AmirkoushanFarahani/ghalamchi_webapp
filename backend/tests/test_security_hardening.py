import asyncio

from backend.app.core.request_limits import RequestBodyLimitMiddleware
from backend.app.db.database import SessionLocal
from backend.app.db.models import User
from backend.tests.test_school_api import school_users
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_credential_version_revokes_existing_session(client: TestClient) -> None:
    _, employee = school_users(client)
    assert client.get('/api/v1/auth/me', headers=employee).status_code == 200
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.email == 'employee@example.com'))
        assert user is not None
        user.session_version += 1
    assert client.get('/api/v1/auth/me', headers=employee).status_code == 401


def test_unassigned_secretary_cannot_fall_back_to_another_school(client: TestClient) -> None:
    _, employee = school_users(client)
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.email == 'employee@example.com'))
        assert user is not None
        user.school_institute_id = None
    assert client.get('/api/v1/school/students', headers=employee).status_code == 403


def test_api_security_headers(client: TestClient) -> None:
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 401
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-request-id']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'camera=()' in response.headers['permissions-policy']


def test_chunked_request_limit() -> None:
    async def scenario() -> None:
        called = False
        messages = iter([
            {'type': 'http.request', 'body': b'123', 'more_body': True},
            {'type': 'http.request', 'body': b'456', 'more_body': False},
        ])
        output = []

        async def application(scope, receive, send):
            nonlocal called
            called = True

        async def receive():
            return next(messages)

        async def send(message):
            output.append(message)

        middleware = RequestBodyLimitMiddleware(application, max_bytes=5)
        await middleware({'type': 'http', 'headers': []}, receive, send)
        assert not called
        assert output[0]['status'] == 413

    asyncio.run(scenario())
