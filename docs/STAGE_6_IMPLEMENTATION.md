# Stage 6 — ML Integration

Implementation date: 2026-08-25

## Scope

Stage 6 connects the four Stage 5 artifacts to FastAPI and PostgreSQL. It adds
no training in the web process, background scheduler, final frontend, dashboard
UI, Persian/RTL work, or Stage 7/8 functionality.

## Architecture and lifecycle

Thin authenticated routes call `MLService`; the service uses `MLRepository` for
accounting/ML queries and `ArtifactRegistry` plus `ModelCache` for inference.
Training, registration, activation, inference, and feedback are distinct.
Registration accepts only controlled identifiers below `ML_MODEL_DIR` and
validates pipeline, artifact/feature schema, version, fingerprint, and runtime
dependency compatibility. The lock-protected cache loads an active version once
and is invalidated on replacement.

## Database

Migration `20260825_0003` adds `ml_model_versions`, `ml_predictions`, and
`ml_prediction_feedback`. PostgreSQL JSONB stores validated metadata and output
structures. Checks constrain pipeline, confidence, and feedback type; foreign
keys preserve model/prediction history. A partial unique index enforces one
active version per pipeline. Predictions and feedback have no update/delete API.

## Pipeline integration

- Transaction classification accepts text, uses the application-configured
  confidence threshold, avoids storing raw text, and persists category,
  confidence, review flag, source reference, model, requester, and timestamp.
- Payment risk builds Stage 5 features from the selected invoice and prior
  customer invoices/payments visible through `as_of`; it persists probability,
  risk category, and top model-level heuristic signals.
- Cash-flow forecasting uses posted payments through `as_of` for an inference
  level adjustment, forecasts 1–365 daily points without retraining, and stores
  values and intervals as one prediction record.
- Customer segmentation aggregates invoices, payments, delays, outstanding
  balance, and frequency through `as_of`, then returns the existing
  centroid-derived behavioral description rather than treating a cluster ID as
  a business label.

## Security and audit

`ml:read` permits safe metadata/history reads; `ml:predict` permits inference;
`ml:feedback` permits append-only feedback; `ml:manage` permits registration and
activation. ADMIN has all permissions; ACCOUNTANT and MANAGER can predict and
submit feedback; VIEWER remains read-only. Registration, activation, and
feedback create security-filtered audit events. APIs expose no artifact paths,
raw transaction text, credentials, tokens, or arbitrary payload storage.

## API

Stage 6 implements model listing/active lookup/registration/activation, four
prediction endpoints, prediction history/detail, and feedback below
`/api/v1/ml`. Errors map safely to 404/409/422/503 without filesystem paths or
loader traces.

## Verification

- Baseline: 57 Stage 1–5 tests passed; Alembic head `20260818_0002`.
- Final backend/ML suite: 67 passed, 96% combined coverage; ML routes 100%, ML
  service 91%, registry 90%.
- Ruff: passed. Strict mypy: passed across 82 files.
- Frontend technical-shell production build: passed with 30 modules.
- Alembic: upgrade, downgrade to `20260818_0002`, upgrade to
  `20260825_0003`, and no-drift check passed on PostgreSQL 16.
- Compose config and fresh Python 3.12 image rebuild passed; ports remain
  8100→8000 and 4173→80, PostgreSQL remains internal.
- Live protected API registered and activated `transaction-v1`, returned a
  `travel` prediction at confidence 0.829806, persisted it, appended feedback,
  and produced three ML audit events. PostgreSQL counts confirmed one model,
  one prediction, one feedback record, and five ML permissions.
- PostgreSQL/backend health, frontend HTTP 200, model-volume loading, RBAC
  401/403/authorized behavior, leakage boundaries, cache replacement, and
  `git diff --check` passed.

## Known limitations

- Registered Stage 5 artifacts and reported metrics are synthetic/demo quality,
  not validated production models.
- Model cache is per process; multi-worker invalidation will need a shared
  notification mechanism before horizontally scaled deployment.
- Cash-flow level adjustment is intentionally simple and residual intervals do
  not model changing volatility.
- Persisted cash-flow history currently contains customer receipts only because
  the accounting domain has no supplier-payment/outflow workflow yet.
- Feedback is captured for later retraining analysis; Stage 6 does not schedule
  retraining or automatically change active models.

## Result

Stage 6 is **PASS**. Stage 7 was not started.
