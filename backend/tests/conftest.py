import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

if os.environ.get("DATABASE_URL") not in {
    None,
    "sqlite+pysqlite:///:memory:",
    "sqlite:///:memory:",
}:
    raise RuntimeError(
        "Backend unit tests require an in-memory SQLite DATABASE_URL; "
        "refusing to create/drop tables in an external database. "
        "Use the dedicated isolated PostgreSQL verification scripts instead."
    )
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-only-secret-that-is-at-least-32-characters")
os.environ.setdefault("ML_MODEL_DIR", ".test-models")

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.db.base import Base  # noqa: E402
from backend.app.db.bootstrap import seed_rbac  # noqa: E402
from backend.app.db.database import SessionLocal, engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.ml.registry import model_cache  # noqa: E402
from ml.config import MLConfig  # noqa: E402
from scripts.train_ml import train_all  # noqa: E402


@pytest.fixture(scope="session")
def ml_artifact_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("stage6-models")
    train_all(path, MLConfig(random_seed=42))
    return path


@pytest.fixture(autouse=True)
def database_schema(ml_artifact_dir: Path) -> Iterator[None]:
    get_settings().ML_MODEL_DIR = ml_artifact_dir
    model_cache.clear()
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        seed_rbac(session)
    yield
    model_cache.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
