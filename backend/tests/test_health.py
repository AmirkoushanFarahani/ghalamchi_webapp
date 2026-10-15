from backend.app.core.config import get_settings
from backend.app.main import app, create_app
from fastapi.testclient import TestClient


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "backend"


def test_readiness_check_queries_required_database() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "backend"


def test_security_headers_and_https_only_hsts() -> None:
    with TestClient(app) as http_client:
        http_response = http_client.get("/api/v1/health")
    with TestClient(app, base_url="https://testserver") as https_client:
        https_response = https_client.get("/api/v1/health")

    assert http_response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    assert http_response.headers["x-content-type-options"] == "nosniff"
    assert http_response.headers["x-frame-options"] == "DENY"
    assert http_response.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in http_response.headers
    assert https_response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_production_disables_api_docs_and_hides_unexpected_errors() -> None:
    production_settings = get_settings().model_copy(update={"APP_ENV": "production"})
    production_app = create_app(production_settings)

    @production_app.get("/unexpected-error")
    def unexpected_error() -> None:
        raise RuntimeError("sensitive traceback detail")

    with TestClient(production_app, raise_server_exceptions=False) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "sensitive traceback detail" not in response.text
