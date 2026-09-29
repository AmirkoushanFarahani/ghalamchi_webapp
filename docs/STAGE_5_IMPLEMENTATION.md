# Stage 5 — Offline Machine Learning Pipelines

Implementation date: 2026-08-24

## Scope and architecture

Stage 5 implements only offline ML preparation, training, evaluation,
artifacts, inference interfaces, tests, and documentation. `ml/` has no FastAPI,
ORM, registry-table, prediction-persistence, feedback, endpoint, worker, or UI
integration. Existing accounting and reporting behavior is unchanged.

## Implemented models

| Pipeline | Method | Evaluation | Seed-42 synthetic result |
|---|---|---|---|
| Transaction classification | TF-IDF + NB versus calibrated linear SVM | seeded stratified 75/25; macro F1 then accuracy selection | accuracy 0.9244, macro F1 0.9247 |
| Payment-delay risk | Random Forest, point-in-time behavioral features | chronological 70/15/15; >7 days late target | accuracy 0.8167, F1 0.6024, ROC AUC 0.8192 |
| Daily cash flow | trend + weekly/monthly/annual harmonic regression | final 30 days chronological backtest | MAE 70.4534, RMSE 93.3948 |
| Customer segmentation | train-fitted scaling + K-Means k=2..6 | inertia and silhouette | silhouette 0.5880 |

These are **DEMO/SYNTHETIC METRICS**, not real-world performance estimates.

## Data and leakage controls

Seed 42 produces 900 transaction rows, 1,200 invoice/payment rows, 500 daily
cash-flow rows, and 260 customer rows. All carry `is_synthetic=True` and include
overlapping profiles and random noise. Text preprocessing is fitted inside each
training-only candidate pipeline. Payment features are built at invoice time
from earlier invoices and already completed payments. Forecasting is always
sorted and split chronologically. The segmentation scaler fits only its training
partition. Dedicated tests enforce all four boundaries.

## Artifact contract

Artifacts live under ignored `ml/models/<pipeline>/<version>/`. `model.joblib`
contains the complete estimator/preprocessor state; `metadata.json` contains
artifact schema, pipeline/model version, UTC timestamp, SHA-256 data fingerprint,
feature schema, seed, configuration, metrics, dependency versions, and synthetic
status. Loaders validate schema and pipeline compatibility, and round-trip tests
compare inference outputs.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev,ml]"
.\.venv\Scripts\python.exe scripts\generate_ml_data.py --seed 42
.\.venv\Scripts\python.exe scripts\train_ml.py
.\.venv\Scripts\python.exe -m pytest backend\tests ml\tests
```

`ML_RANDOM_SEED`, `ML_CONFIDENCE_THRESHOLD`, `ML_RISK_DELAY_DAYS`, and
`ML_FORECAST_HORIZON` configure the offline workflow. Prophet was not added;
the documented deterministic harmonic regression fallback avoids a heavy
compiled stack while remaining compatible with the supported Python 3.12 image.

## Verification

- Baseline before ML changes: 46 backend tests passed.
- Final complete suite: 57 tests passed; combined backend/ML coverage 96%.
- ML tests: 11 passed, including leakage, repeatability, metadata, and all four
  artifact save/load paths.
- Ruff: passed. Strict mypy: passed across 73 source files.
- Synthetic generation and all four training/evaluation runs: passed.
- Frontend technical-shell production build: passed (30 modules).
- `docker compose config`: passed; ports remain backend 8100→8000 and frontend
  4173→80.
- Fresh Compose build: passed on Python 3.12; PostgreSQL/backend healthy and
  frontend running. Host backend and frontend checks both returned HTTP 200.
- PostgreSQL remains on Alembic head `20260818_0002`; Stage 5 adds no migration.
- `git diff --check`: passed.

## Limitations

- Synthetic profiles cannot validate deployment accuracy, fairness, calibration,
  drift, seasonality changes, or operational value.
- Risk contributions are impurity-weighted model heuristics, not causal claims.
- Forecast intervals use residual variance and do not model changing volatility.
- Artifacts are local files; registry, persisted predictions, feedback, APIs,
  authorization, and scheduling belong to Stage 6 or later.

## Result

Stage 5 is **PASS**. Stage 5 complete. Stage 6 was not started.
