# Stage 4 — Reports and Dashboard API

Implementation date: 2026-08-18

## Authoritative scope

The repository roadmap defines Stage 4 as statements, receivables/payables,
filters, and dashboard aggregates derived from persisted records. The original
project specification expands the report list to income, expenses, revenue,
cash flow, and party histories. The roadmap places ML in Stage 5 and the full
frontend in Stage 7, so neither is part of Stage 4.

## Reporting design

`ReportingRepository` contains aggregate queries over Stage 3 records.
`ReportingService` applies date validation, account normal-balance semantics,
historical allocation logic, report totals, and dashboard composition. Reports
are read-only and use `Decimal`; they neither mutate nor bypass the accounting
posting engine.

Financial statements include POSTED journals only. Trial balance reports raw
debits/credits and verifies equality. Income statement treats REVENUE as a
credit-normal balance and EXPENSE as debit-normal. Balance sheet includes
current unclosed earnings so assets can be compared with liabilities, equity,
and current earnings.

Historical receivables calculate paid-as-of from allocations linked to POSTED
payments dated on or before the requested date. This avoids leaking later
payments into earlier snapshots. Overdue state and days are derived from due
date and the historical balance.

## API

All endpoints require `reports:read`:

- `/reports/trial-balance`
- `/reports/income-statement`
- `/reports/revenue`
- `/reports/expenses`
- `/reports/balance-sheet`
- `/reports/receivables`
- `/reports/payables`
- `/reports/cash-flow`
- `/reports/parties/{party_id}/history`
- `/dashboard`

Date/as-of and customer filters are optional. Invalid ranges return 422,
unauthenticated requests return 401, and missing parties return 404.

## Database

Stage 4 adds no tables. Index-only migration `20260818_0002` supports journal,
invoice, payment, and allocation report filters. Alembic reports no drift.

## Verification

- Stage 3 baseline: 42 tests passed with 93% accounting-service coverage.
- Complete suite: 46 tests passed with 95% application coverage.
- Reporting repository: 100% coverage; reporting service: 99% coverage.
- Report calculations, posted-only behavior, date filters, historical AR,
  overdue derivation, payable exposure, cash receipts, dashboard, 401, and API
  response-shape tests passed.
- PostgreSQL: isolated migration, no-drift check, and Decimal report aggregation
  passed; `azari_stage4_test` was removed afterward.
- Strict mypy: no issues in 54 source files.
- Ruff: passed.
- Frontend production build: passed with 30 modules transformed.
- Compose: PostgreSQL/backend healthy; backend 8100→8000 and frontend 4173→80.
- Backend health, frontend, OpenAPI, and report-route runtime checks passed.
- `git diff --check`: passed.

## Limitations

- Stage 3 has no supplier-bill/payable document or supplier allocation model.
  The payables report therefore truthfully exposes posted LIABILITY-account
  balances but cannot produce supplier-level payable aging.
- Cash flow currently reports posted customer cash receipts. Outgoing supplier
  cash flows require the future payable/payment-out workflow.
- The operational dashboard is API-only; the full UI is intentionally Stage 7.
- ML risk and forecast metrics are intentionally absent until Stage 5/6.

## Result

Stage 4 is **PASS**. Stage 5 and ML have not started.
