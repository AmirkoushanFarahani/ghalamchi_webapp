# Azari Intelligent Accounting

An academic, production-oriented accounting application integrating
double-entry bookkeeping with transaction classification, payment-delay risk,
cash-flow forecasting, and customer/supplier segmentation.

The repository is being implemented in verified milestones. Stage 1 provides
the runnable three-service foundation; Stage 2 adds PostgreSQL persistence,
identity, JWT authentication, database-backed RBAC, and security audit events.
Stage 3 adds the transactional double-entry accounting vertical slice. See
[PROJECT_ANALYSIS.md](docs/PROJECT_ANALYSIS.md) for the audit, architecture, risks,
and roadmap.

Stage 7 adds the complete Persian/RTL web application: authenticated and
permission-aware accounting workflows, statements and operational dashboard,
dual Jalali/Gregorian dates, responsive navigation, light/dark themes, and all
four Stage 6 AI workflows. Open it at `http://localhost:4173` after startup.

Stage 8 completes the production-readiness pass: accounting/API integration,
security and log review, Persian/mobile/accessibility fixes, all four live ML
workflows, restart persistence, and a non-root backend image.

## Quick start

1. Copy `.env.example` to `.env` and replace every `change-me` value.
2. With Docker installed, run `docker compose up --build`.
3. Open the frontend at `http://localhost:4173` and API documentation at
   `http://localhost:8100/docs`.

Local backend and frontend setup is documented in [docs/SETUP.md](docs/SETUP.md).
For a source-verified explanation of the complete current system in English and
Persian, read [HOW_THE_PROJECT_WORKS.md](docs/HOW_THE_PROJECT_WORKS.md). The stage
documents below are historical delivery records rather than the current-state
reference.

## Stage 2 identity API

- `POST /api/v1/auth/register` creates an Argon2-hashed ADMIN account with at
  least one unique email address or E.164 phone number.
- `POST /api/v1/auth/login` accepts either email/password or phone/password and
  returns a short-lived bearer access token.
- `GET /api/v1/auth/me` returns the authenticated user without password data.
- `GET /api/v1/users` requires the database permission `users:read`.

Compose applies Alembic migrations and idempotently seeds roles/permissions
before starting the development API. It never creates an administrator unless
both optional bootstrap environment variables are explicitly set.

## Stage 3 accounting API

Authenticated, permission-protected APIs now manage parties, products, the
chart of accounts, financial periods, draft/post/reverse journals, invoices,
payments, and allocations. Invoice issuance and payment posting use the same
balanced journal posting engine. See [STAGE_3_IMPLEMENTATION.md](docs/STAGE_3_IMPLEMENTATION.md).

## Stage 4 reports API

Stage 4 adds read-only financial statements, revenue/expense summaries,
historical receivables, liability-account payable exposure, customer history,
cash receipts, and operational dashboard aggregates protected by
`reports:read`. Receivables and dashboard totals include only issued accounting
documents; draft invoices do not affect posted financial values.

## Stage 5 offline ML

Stage 5 adds four framework-independent pipelines under `ml/`: calibrated
TF-IDF transaction classification, timestamp-safe Random Forest payment risk,
deterministic harmonic cash-flow forecasting, and scaled K-Means customer
segmentation. They use explicitly synthetic development data. At Stage 5 they
were not yet wired to HTTP or the database; Stage 6 added that integration.

```powershell
.\.venv\Scripts\python.exe scripts\generate_ml_data.py --seed 42
.\.venv\Scripts\python.exe scripts\train_ml.py
```

Generated CSVs and versioned artifacts are ignored by Git. See
[docs/ML.md](docs/ML.md) and [STAGE_5_IMPLEMENTATION.md](docs/STAGE_5_IMPLEMENTATION.md).

## Stage 6 ML integration

Stage 6 connects those artifacts to PostgreSQL and protected `/api/v1/ml`
endpoints through a database-backed registry, active-version selection,
thread-safe artifact cache, append-only predictions, feedback, RBAC, and audit
events. It uses real persisted invoice/payment/customer history at explicit
cutoffs where applicable. Training remains offline; registration and activation
are ADMIN-only through `ml:manage`. See
[STAGE_6_IMPLEMENTATION.md](docs/STAGE_6_IMPLEMENTATION.md).

## Stage 7 production frontend

The React application is now a Persian business interface rather than a
technical health shell. It uses the existing JWT and RBAC contracts, sends all
accounting and report data through the versioned API, and never substitutes
sample values for absent records. Desktop navigation uses the top bar; narrower
tablet and mobile layouts use a right-side drawer. Light is the default theme and the
dark theme and calendar choice persist locally.

Frontend developer and test commands are in [frontend/README.md](frontend/README.md).
Implementation and verification details are in
[STAGE_7_IMPLEMENTATION.md](docs/STAGE_7_IMPLEMENTATION.md).

## Stage 8 production readiness

The Stage 8 suite verifies accounting reconciliation and rollback, API
authentication/RBAC, reports, all registered ML pipelines, feedback and
low-confidence review, responsive Persian presentation, Compose health,
migrations, and persisted data after restart. Remaining synthetic-ML and
product-scope limitations are explicit in
[STAGE_8_IMPLEMENTATION.md](docs/STAGE_8_IMPLEMENTATION.md).
