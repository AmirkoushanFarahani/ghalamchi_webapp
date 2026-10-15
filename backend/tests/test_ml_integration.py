from __future__ import annotations

import json
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from backend.app.core.config import get_settings
from backend.app.core.passwords import hash_password
from backend.app.db.database import SessionLocal
from backend.app.db.models import (
    AuditEvent,
    Invoice,
    MLModelVersion,
    MLPredictionFeedback,
    Party,
    Payment,
    PaymentAllocation,
    Role,
    User,
)
from backend.app.ml.registry import (
    ArtifactRegistry,
    ArtifactValidationError,
    PredictionExecutionError,
    PredictionInputError,
)
from backend.app.schemas.ml import FeedbackRequest, TransactionClassifyRequest
from backend.app.services.ml import MLService
from fastapi.testclient import TestClient
from sqlalchemy import select


def add_user(role_name: str, email: str) -> User:
    with SessionLocal.begin() as session:
        role = session.scalar(select(Role).where(Role.name == role_name))
        user = User(
            email=email,
            password_hash=hash_password("stage-six-password"),
            first_name="Stage",
            last_name="Six",
            roles=[role],
        )
        session.add(user)
    return user


def headers_for(client: TestClient, role: str, email: str) -> dict[str, str]:
    add_user(role, email)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "stage-six-password"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_all(service: MLService, actor: User) -> dict[str, MLModelVersion]:
    identifiers = {
        "transaction_classification": "transaction/transaction-v1",
        "payment_delay_risk": "payment-risk/payment-risk-v1",
        "cash_flow_forecast": "cash-flow/cash-flow-v1",
        "customer_segmentation": "segmentation/customer-segments-v1",
    }
    records = {
        pipeline: service.register_model(pipeline, identifier, actor)
        for pipeline, identifier in identifiers.items()
    }
    for record in records.values():
        service.activate_model(record.id, actor)
    return records


def accounting_history(owner_email: str) -> tuple[Party, Invoice]:
    with SessionLocal.begin() as session:
        owner = session.scalar(select(User).where(User.email == owner_email))
        assert owner is not None
        party = Party(owner_id=owner.id, name="ML Customer", is_customer=True)
        session.add(party)
        session.flush()
        first = Invoice(
            owner_id=owner.id,
            invoice_number="ML-I-1",
            customer_id=party.id,
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 15),
            status="PAID",
            subtotal=Decimal("100"),
            tax=Decimal("0"),
            total=Decimal("100"),
            amount_paid=Decimal("100"),
        )
        current = Invoice(
            owner_id=owner.id,
            invoice_number="ML-I-2",
            customer_id=party.id,
            issue_date=date(2026, 2, 1),
            due_date=date(2026, 2, 15),
            status="ISSUED",
            subtotal=Decimal("250"),
            tax=Decimal("0"),
            total=Decimal("250"),
            amount_paid=Decimal("0"),
        )
        payment = Payment(
            owner_id=owner.id,
            party_id=party.id,
            payment_date=date(2026, 1, 20),
            amount=Decimal("100"),
            reference="ML-P-1",
            method="bank",
            status="POSTED",
        )
        session.add_all([first, current, payment])
        session.flush()
        session.add(PaymentAllocation(payment_id=payment.id, invoice_id=first.id, amount=100))
    return party, current


def test_artifact_registry_rejects_missing_traversal_and_schema(
    ml_artifact_dir: Path, tmp_path: Path
) -> None:
    registry = ArtifactRegistry(ml_artifact_dir)
    with pytest.raises(ArtifactValidationError, match="identifier"):
        registry.validate("transaction_classification", "../secret")
    with pytest.raises(ArtifactValidationError, match="unavailable"):
        registry.validate("transaction_classification", "transaction/missing")

    broken_root = tmp_path / "models"
    broken = broken_root / "transaction" / "broken-v1"
    shutil.copytree(ml_artifact_dir / "transaction" / "transaction-v1", broken)
    metadata_path = broken / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["model_version"] = "broken-v1"
    metadata["feature_schema"] = ["wrong"]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="validation failed"):
        ArtifactRegistry(broken_root).validate(
            "transaction_classification", "transaction/broken-v1"
        )


def test_registration_never_deserializes_and_tampered_artifact_cannot_activate(
    ml_artifact_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "models"
    shutil.copytree(ml_artifact_dir, artifact_root)
    settings = get_settings()
    settings.ML_MODEL_DIR = artifact_root
    load_calls = 0

    def unsafe_load(*args: object, **kwargs: object) -> object:
        nonlocal load_calls
        load_calls += 1
        raise AssertionError("untrusted joblib was deserialized")

    monkeypatch.setattr("ml.common.joblib.load", unsafe_load)
    with SessionLocal() as session:
        actor = session.merge(add_user("ADMIN", "artifact-security@example.com"))
        service = MLService(session, settings)
        record = service.register_model(
            "transaction_classification", "transaction/transaction-v1", actor
        )
        assert load_calls == 0

        model_path = artifact_root / "transaction" / "transaction-v1" / "model.joblib"
        with model_path.open("ab") as artifact:
            artifact.write(b"tampered")

        with pytest.raises(PredictionExecutionError, match="integrity") as failure:
            service.activate_model(record.id, actor)
        assert load_calls == 0
        assert str(artifact_root) not in str(failure.value)


def test_unpinned_artifact_cannot_be_loaded(ml_artifact_dir: Path) -> None:
    registry = ArtifactRegistry(ml_artifact_dir)
    with pytest.raises(ArtifactValidationError, match="not been approved"):
        registry.load(
            "transaction_classification", "transaction/transaction-v1", None
        )


def test_writable_artifact_cannot_load_as_a_production_model(
    ml_artifact_dir: Path,
) -> None:
    registry = ArtifactRegistry(ml_artifact_dir, require_read_only=True)
    _, digest = registry.validate(
        "transaction_classification", "transaction/transaction-v1"
    )
    with pytest.raises(ArtifactValidationError, match="read-only"):
        registry.load(
            "transaction_classification",
            "transaction/transaction-v1",
            digest,
        )


def test_registry_activation_cache_and_single_active_version(
    ml_artifact_dir: Path, tmp_path: Path
) -> None:
    second_root = tmp_path / "models"
    shutil.copytree(ml_artifact_dir, second_root)
    second = second_root / "transaction" / "transaction-v2"
    shutil.copytree(second_root / "transaction" / "transaction-v1", second)
    metadata_path = second / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["model_version"] = "transaction-v2"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    settings = get_settings()
    settings.ML_MODEL_DIR = second_root

    with SessionLocal() as session:
        actor = session.merge(add_user("ADMIN", "registry@example.com"))
        service = MLService(session, settings)
        first = service.register_model(
            "transaction_classification", "transaction/transaction-v1", actor
        )
        second_record = service.register_model(
            "transaction_classification", "transaction/transaction-v2", actor
        )
        service.activate_model(first.id, actor)
        first_prediction, _ = service.classify_transaction("hotel booking business", actor)
        assert first_prediction.model_version_id == first.id
        service.activate_model(second_record.id, actor)
        second_prediction, value = service.classify_transaction("hotel booking business", actor)
        assert second_prediction.model_version_id == second_record.id
        assert value["model_version"] == "transaction-v2"
        assert sum(item.is_active for item in service.models("transaction_classification")) == 1


def test_model_cache_loads_an_active_artifact_once(
    ml_artifact_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    original = ArtifactRegistry.validate

    def counted_validate(
        registry: ArtifactRegistry, pipeline: str, identifier: str
    ) -> tuple[object, object]:
        nonlocal calls
        calls += 1
        return original(registry, pipeline, identifier)

    monkeypatch.setattr(ArtifactRegistry, "validate", counted_validate)
    with SessionLocal() as session:
        actor = session.merge(add_user("ADMIN", "cache@example.com"))
        service = MLService(session, get_settings())
        record = service.register_model(
            "transaction_classification", "transaction/transaction-v1", actor
        )
        service.activate_model(record.id, actor)
        calls = 0
        service.classify_transaction("hotel booking business", actor)
        service.classify_transaction("hotel booking business", actor)
        assert calls == 1


def test_all_four_predictions_persist_use_real_history_and_feedback() -> None:
    owner = add_user("ADMIN", "predictions@example.com")
    party, invoice = accounting_history("predictions@example.com")
    with SessionLocal() as session:
        actor = session.merge(owner)
        service = MLService(session, get_settings())
        register_all(service, actor)
        transaction, transaction_value = service.classify_transaction(
            "metro hotel booking business", actor, "JOURNAL-REF"
        )
        risk, risk_value = service.payment_risk(invoice.id, date(2026, 2, 10), actor)
        forecast, points = service.cash_flow_forecast(7, date(2026, 2, 10), actor)
        segment, segment_value = service.segment_customer(party.id, date(2026, 2, 10), actor)

        assert transaction_value["category"] and transaction.confidence is not None
        assert risk_value["scope"] == "model-level heuristic"
        assert risk.confidence is not None and risk.source_id == str(invoice.id)
        assert len(points) == 7 and forecast.predicted_value["as_of"] == "2026-02-10"
        assert "customers" in segment_value["behavioral_description"]
        assert len(service.predictions(actor)) == 4

        first = service.submit_feedback(
            transaction.id,
            FeedbackRequest(feedback_type="VERIFIED", actual_value="travel"),
            actor,
        )
        second = service.submit_feedback(
            transaction.id,
            FeedbackRequest(feedback_type="COMMENT", comment="Reviewed independently"),
            actor,
        )
        assert first.id != second.id
        assert len(session.scalars(select(MLPredictionFeedback)).all()) == 2
        actions = set(session.scalars(select(AuditEvent.action)).all())
        assert {"ml.model.register", "ml.model.activate", "ml.prediction.feedback"} <= actions


def test_application_confidence_threshold_controls_manual_review() -> None:
    settings = get_settings()
    previous = settings.ML_CONFIDENCE_THRESHOLD
    settings.ML_CONFIDENCE_THRESHOLD = 1.0
    try:
        with SessionLocal() as session:
            actor = session.merge(add_user("ADMIN", "threshold@example.com"))
            service = MLService(session, settings)
            record = service.register_model(
                "transaction_classification", "transaction/transaction-v1", actor
            )
            service.activate_model(record.id, actor)
            prediction, _ = service.classify_transaction("hotel booking business", actor)
            assert prediction.review_required
    finally:
        settings.ML_CONFIDENCE_THRESHOLD = previous


def test_payment_and_cash_flow_as_of_boundaries_exclude_future_data() -> None:
    owner = add_user("ADMIN", "boundaries@example.com")
    party, invoice = accounting_history("boundaries@example.com")
    with SessionLocal() as session:
        service = MLService(session, get_settings())
        actor = session.merge(owner)
        before = service._payment_features(
            invoice.id, party.id, 250.0, date(2026, 2, 10), actor.id
        )
        future = Payment(
            owner_id=actor.id,
            party_id=party.id,
            payment_date=date(2026, 3, 1),
            amount=Decimal("50"),
            reference="ML-FUTURE",
            method="bank",
            status="POSTED",
        )
        session.add(future)
        session.flush()
        session.add(PaymentAllocation(payment_id=future.id, invoice_id=invoice.id, amount=50))
        session.commit()
        after = service._payment_features(
            invoice.id, party.id, 250.0, date(2026, 2, 10), actor.id
        )
        assert before == after
        assert all(
            payment.payment_date <= date(2026, 2, 10)
            for payment in service.repo.posted_payments(date(2026, 2, 10), actor.id)
        )


def test_ml_api_security_management_prediction_history_and_feedback(client: TestClient) -> None:
    assert client.get("/api/v1/ml/models").status_code == 401
    viewer = headers_for(client, "VIEWER", "ml-viewer@example.com")
    assert client.get("/api/v1/ml/models", headers=viewer).status_code == 200
    assert (
        client.post(
            "/api/v1/ml/models/register",
            headers=viewer,
            json={
                "pipeline": "transaction_classification",
                "artifact_identifier": "transaction/transaction-v1",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/ml/transactions/classify",
            headers=viewer,
            json={"description": "hotel booking"},
        ).status_code
        == 403
    )

    owner = headers_for(client, "OWNER", "ml-owner@example.com")
    admin = headers_for(client, "ADMIN", "ml-platform-admin@example.com")
    assert client.post(
        "/api/v1/ml/models/register", headers=owner,
        json={"pipeline": "transaction_classification", "artifact_identifier": "transaction/transaction-v1"},
    ).status_code == 403
    registered = client.post(
        "/api/v1/ml/models/register",
        headers=admin,
        json={
            "pipeline": "transaction_classification",
            "artifact_identifier": "transaction/transaction-v1",
        },
    )
    assert registered.status_code == 201
    assert "artifact_identifier" not in registered.json()
    assert client.post(f"/api/v1/ml/models/{registered.json()['id']}/activate", headers=owner).status_code == 403
    activated = client.post(f"/api/v1/ml/models/{registered.json()['id']}/activate", headers=admin)
    assert activated.status_code == 200 and activated.json()["is_active"]
    predicted = client.post(
        "/api/v1/ml/transactions/classify",
        headers=owner,
        json={"description": "metro hotel booking business"},
    )
    assert predicted.status_code == 200
    prediction_id = predicted.json()["prediction_id"]
    history = client.get("/api/v1/ml/predictions", headers=owner)
    assert history.status_code == 200 and history.json()[0]["id"] == prediction_id
    feedback = client.post(
        f"/api/v1/ml/predictions/{prediction_id}/feedback",
        headers=owner,
        json={"feedback_type": "CORRECTION", "actual_value": "travel"},
    )
    assert feedback.status_code == 201
    assert client.get(f"/api/v1/ml/predictions/{prediction_id}", headers=owner).json()["feedback"]


def test_invalid_feedback_and_no_active_model_are_safe(client: TestClient) -> None:
    admin = headers_for(client, "ADMIN", "ml-errors@example.com")
    assert (
        client.post(
            "/api/v1/ml/transactions/classify", headers=admin, json={"description": "hotel booking"}
        ).status_code
        == 404
    )
    response = client.post(
        f"/api/v1/ml/predictions/{uuid4()}/feedback",
        headers=admin,
        json={"feedback_type": "CORRECTION"},
    )
    assert response.status_code == 422


def test_ml_rejects_blank_classification_and_draft_payment_risk() -> None:
    with pytest.raises(ValueError):
        TransactionClassifyRequest(description="   ")

    owner = add_user("ADMIN", "draft-risk@example.com")
    party, invoice = accounting_history("draft-risk@example.com")
    with SessionLocal() as session:
        actor = session.merge(owner)
        current = session.get(Invoice, invoice.id)
        assert current is not None
        current.status = "DRAFT"
        session.commit()
        service = MLService(session, get_settings())
        with pytest.raises(PredictionInputError, match="issued invoice"):
            service.payment_risk(current.id, date(2026, 2, 10), actor)


def test_all_pipeline_api_response_shapes_and_feedback_permission(client: TestClient) -> None:
    admin = headers_for(client, "ADMIN", "ml-api-all@example.com")
    party, invoice = accounting_history("ml-api-all@example.com")
    viewer = headers_for(client, "VIEWER", "ml-feedback-viewer@example.com")
    identifiers = {
        "transaction_classification": "transaction/transaction-v1",
        "payment_delay_risk": "payment-risk/payment-risk-v1",
        "cash_flow_forecast": "cash-flow/cash-flow-v1",
        "customer_segmentation": "segmentation/customer-segments-v1",
    }
    for pipeline, identifier in identifiers.items():
        registered = client.post(
            "/api/v1/ml/models/register",
            headers=admin,
            json={"pipeline": pipeline, "artifact_identifier": identifier},
        )
        assert registered.status_code == 201
        assert (
            client.post(
                f"/api/v1/ml/models/{registered.json()['id']}/activate", headers=admin
            ).status_code
            == 200
        )
        active = client.get(f"/api/v1/ml/models/{pipeline}/active", headers=admin)
        assert active.status_code == 200 and active.json()["model_version"]

    risk = client.post(
        "/api/v1/ml/payment-risk/predict",
        headers=admin,
        json={"invoice_id": str(invoice.id), "as_of": "2026-02-10"},
    )
    assert risk.status_code == 200
    assert risk.json()["explanation_scope"] == "model-level heuristic"
    assert 0 <= risk.json()["probability"] <= 1

    forecast = client.post(
        "/api/v1/ml/cash-flow/forecast",
        headers=admin,
        json={"horizon": 5, "as_of": "2026-02-10"},
    )
    assert forecast.status_code == 200 and len(forecast.json()["points"]) == 5
    assert {"predicted", "lower", "upper"} <= set(forecast.json()["points"][0])
    assert forecast.json()["points"][0]["date"] == "2026-02-11"

    segment = client.post(
        "/api/v1/ml/segmentation/predict",
        headers=admin,
        json={"party_id": str(party.id), "as_of": "2026-02-10"},
    )
    assert segment.status_code == 200
    assert "customers" in segment.json()["behavioral_description"]
    assert (
        client.post(
            f"/api/v1/ml/predictions/{risk.json()['prediction_id']}/feedback",
            headers=viewer,
            json={"feedback_type": "VERIFIED", "actual_value": "high"},
        ).status_code
        == 403
    )


def test_prediction_records_have_no_mutation_api(client: TestClient) -> None:
    admin = headers_for(client, "ADMIN", "ml-immutable@example.com")
    assert (
        client.patch(
            "/api/v1/ml/predictions/00000000-0000-0000-0000-000000000000", headers=admin
        ).status_code
        == 405
    )
    assert (
        client.delete(
            "/api/v1/ml/predictions/00000000-0000-0000-0000-000000000000", headers=admin
        ).status_code
        == 405
    )
