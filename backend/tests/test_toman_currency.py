"""Synthetic currency-boundary/migration tests; never runs against an external DB."""

import runpy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.app.core.currency import from_rials
from backend.app.db.base import Base
from backend.app.db.database import SessionLocal
from backend.app.db.models import DiscountCode, SchoolCourse
from backend.app.services.ml import MLService
from backend.scripts.demo_database import typed_values
from backend.scripts.import_class_catalog import catalog
from backend.tests.test_school_api import school_users
from fastapi.testclient import TestClient
from sqlalchemy import Numeric

MIGRATION = runpy.run_path(
    str(Path(__file__).parents[1] / "alembic" / "versions" / "20261021_0032_toman_currency.py")
)


def test_conversion_inventory_covers_every_money_column_not_counts_rates_or_quantities():
    actual = {
        table.name: tuple(
            column.name
            for column in table.columns
            if isinstance(column.type, Numeric)
            and column.type.precision == 18
            and column.type.scale == 2
        )
        for table in Base.metadata.tables.values()
    }
    # Tables introduced AFTER the currency conversion already store Toman.
    actual = {
        name: columns
        for name, columns in actual.items()
        if columns and name != "school_cost_payments"
    }
    assert {k: set(v) for k, v in actual.items()} == {
        k: set(v) for k, v in MIGRATION["MONEY_COLUMNS"].items()
    }
    assert sum(map(len, actual.values())) == 62


@pytest.mark.parametrize(
    "value,expected", [("10000000", "1000000"), ("1", "0.10"), ("0.1", "0.01"), ("-500", "-50")]
)
def test_rial_sources_convert_exactly(value, expected):
    assert from_rials(value) == Decimal(expected)
    assert MIGRATION["exact_toman"](value) == Decimal(expected)


def test_precision_loss_is_rejected_not_rounded():
    for value in ("0.01", "123.45"):
        with pytest.raises(ValueError):
            from_rials(value)
        with pytest.raises(ValueError):
            MIGRATION["exact_toman"](value)


def test_old_demo_snapshot_converts_money_not_percentages_or_existing_toman():
    assert typed_values(SchoolCourse, {"price": "10000000", "session_count": 20}, "IRR") == {
        "price": Decimal("1000000"),
        "session_count": 20,
    }
    assert typed_values(SchoolCourse, {"price": "1000000"}, "TOMAN")["price"] == Decimal("1000000")
    assert typed_values(DiscountCode, {"percentage": "10"}, "IRR")["percentage"] == Decimal("10")
    rows = catalog()
    assert rows and rows[0].price > 0
    import json

    source = json.loads(
        (Path(__file__).parents[1] / "scripts/data/class_catalog.json").read_text(encoding="utf-8")
    )
    assert rows[0].price == Decimal(source[0]["price"]) / 10


def test_legacy_ml_units_are_adapted_without_changing_counts_or_model_artifacts():
    features = {
        "total_invoice_amount": 1000000.0,
        "avg_invoice_amount": 500000.0,
        "total_payment_amount": 300000.0,
        "outstanding_balance": 700000.0,
        "invoice_count": 2.0,
        "avg_delay_days": 3.0,
        "payment_frequency": 1.0,
    }
    legacy = SimpleNamespace(training_configuration={})
    scaled = MLService._model_money_features(features, legacy)
    assert scaled["total_invoice_amount"] == 10000000
    assert scaled["invoice_count"] == 2 and scaled["avg_delay_days"] == 3
    assert features["total_invoice_amount"] == 1000000  # No in-place mutation.
    assert (
        MLService._model_money_features(
            features, SimpleNamespace(training_configuration={"currency": "TOMAN"})
        )
        == features
    )


def test_conversion_preserves_school_balances_snapshots_and_percentages(client: TestClient):
    manager, secretary = school_users(client)
    course = client.post(
        "/api/v1/school/courses",
        headers=manager,
        json={
            "name": "Synthetic legacy class",
            "grade": "GRADE_4",
            "price": "10000000",
            "session_count": 20,
        },
    ).json()
    client.post(
        "/api/v1/school/discounts", headers=manager, json={"code": "TENOFF", "percentage": "10"}
    )
    student = client.post(
        "/api/v1/school/students/enroll",
        headers=secretary,
        json={
            "full_name": "Synthetic Currency Student",
            "national_id": "9800000010",
            "birth_date": "2015-01-01",
            "grade": "GRADE_4",
            "guardian_full_name": "Synthetic Guardian",
            "guardian_phone": "09120000000",
            "course_ids": [course["id"]],
            "discount_code": "TENOFF",
            "payments": [{"method": "CASH", "amount": "2000000"}],
        },
    ).json()
    old = student["enrollments"][0]
    with SessionLocal.begin() as session:
        MIGRATION["convert_existing_money"](session.connection())
    updated = client.get(f"/api/v1/school/students/{student['id']}", headers=secretary)
    assert updated.headers["X-Monetary-Unit"] == "TOMAN"
    new = updated.json()["enrollments"][0]
    for key in ("subtotal", "discount_amount", "total_amount", "amount_paid", "balance_due"):
        assert Decimal(new[key]) == Decimal(old[key]) / 10
    assert new["courses"][0]["session_count"] == 20
    assert Decimal(new["courses"][0]["price"]) == 1000000
    assert Decimal(new["payments"][0]["amount"]) == 200000
    assert new["status"] == old["status"] and new["academic_year"] == old["academic_year"]
    assert Decimal(new["amount_paid"]) + Decimal(new["balance_due"]) == Decimal(new["total_amount"])
    assert (
        client.get("/api/v1/school/discounts", headers=manager).json()[0]["percentage"] == "10.00"
    )


def test_audit_conversion_changes_amounts_not_identity_counts_or_free_text():
    old = {
        "old_total": "10000000",
        "new_total": "5000000",
        "session_number": 3,
        "reason": "amount 10000000 is original free text",
        "school_id": "10000000",
    }
    converted = MIGRATION["convert_audit_metadata"](old)
    assert converted["old_total"] == "1000000.00" and converted["new_total"] == "500000.00"
    assert converted["currency"] == "TOMAN" and converted["session_number"] == 3
    assert converted["reason"] == old["reason"] and converted["school_id"] == old["school_id"]
