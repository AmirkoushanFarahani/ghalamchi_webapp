# Mixed payments — local implementation

## Active school workflows

The shared Persian/RTL payment planner is used for student registration, tuition
balance replacement (student profile and tuition follow-up pages), positive class
or special-support price differences, and manager-only school cost invoices.
It accepts multiple cash/bank/check portions plus an automatically divided
installment remainder. School supplier purchases can be recorded as cost invoices
with the supplier in `vendor_name`; the older general-accounting bill/payment
screens are not converted into this school payment system.

The server calculates the actual tuition/price difference, then requires the plan
to cover that complete amount. Preview totals are advisory, not trusted prices.
The legacy `payments`/single-payment API fields remain backward compatible for
existing clients, operator demo import and historical partial-payment records;
those interfaces do not acquire the new full-plan requirement automatically.

## Amounts and dates

The simplified selector offers exactly three choices: full immediate payment,
all installments, or upfront payment plus installments. Immediate payment may be
cash or bank transfer. Deferred portions may be normal installments or checks,
not both together in the simplified UI. Check identifiers and date overrides are
optional; the server supplies the monthly due date when none is entered.
There is no fourth mixed-check menu. Legacy explicit check API rows still require
a due date; generated check installments always receive a server-calculated date.

- All amounts are Toman with Decimal precision of two fractional digits.
- Cash and bank transfer are confirmed immediately. Each check has its own amount,
  mandatory due date, optional tracking code and optional Sayad identifier.
- Staff selects installment count, not individual installment amounts/dates.
- First installment is one Persian calendar month after registration/invoice date;
  replacement plans and class/support differences use today's Tehran date.
- Later installments use the original day of the month, clamped to the destination
  Persian month's last day. A short month does not permanently shift later dates.
- Remainder cents are allocated to the first installments, preserving the exact sum.
- Checks/installments remain pending until manually confirmed as received/paid.
  These are manual accounting records, not bank/gateway verification.

## Editing and history

Received payments cannot be changed. Replacing a balance plan cancels only its
pending/bounced portions and appends new portions; cancelled history remains.
All remaining debt must be covered. Clients send the expected balance and pending
IDs. The server locks the parent enrollment/cost and rejects stale replacements.
Cost settlement uses that same parent lock and cannot settle twice.
Class/support price decreases and cancellations retain existing refund/credit
rules; pending checks are not silently rewritten. Staff should explicitly replace
the remaining plan when a fee reduction makes old schedules inappropriate.

## Permissions

Managers and assigned secretaries may manage their own institute's student plans.
Cost records/settlement, institute aggregates and refund disbursement remain
manager-only. New routes require JWT permissions plus workspace/institute scope.
Preview is authenticated POST and does not mutate data.

## Database migration

`20261021_0033` follows Toman conversion `0032`. It adds `school_cost_payments`
and backfills existing costs as PAID, preserving their previous paid-cost meaning.
It does not divide currency again. Existing records and credentials are preserved.
Take a private backup, stop writers, run Alembic upgrade, then restart the backend
and rebuild frontend. The migration intentionally refuses an automatic destructive
downgrade. Local backups are ignored and must never be committed.

## Verification

- Backend regression tests and dedicated `test_mixed_payments.py` cover exact splits,
  Persian month boundaries, invalid coverage, student/cost settlement and replacement,
  immutable received records, class/support differences and cross-institute writes.
- `frontend/tests/mixed-payments.browser.mjs` uses real components with synthetic
  HTTP fixtures; `academic-years.browser.mjs` checks registration remains usable.
- `backend/scripts/verify_mixed_payments.py` refuses non-disposable databases and
  tests concurrent student/cost replacements on PostgreSQL (one success, one conflict).
- Local restored and fresh PostgreSQL migration checks are separate from SQLite tests.

Not a production deployment/security certification. Existing frontend baseline
assertion failures and dependency advisories must remain visible in release reports.

### Local verification — 2026-10-22

- PASS: 207 backend regression tests; Ruff including security rules, configured mypy.
- PASS: frontend production/TypeScript build and both real-browser fixture suites.
- PASS: fresh PostgreSQL migration chain and restored 0032→0033 migration. All six
  historical school costs were backfilled without changing their amounts.
- PASS: PostgreSQL concurrency tests for both student and cost replacements.
- PASS: local Nginx/readiness and authenticated manager/two-secretary preview/list
  requests. No passwords were changed; authentication checks used unprinted tokens.
- PASS: bounded local security scanner checks except expected localhost HTTP warning.
- Remaining baseline: five frontend suite failures (business route equality, number
  precision expectation, two existing API-error assertions, supplier-bill copy).
  Existing Vite dependency advisory and bundle-size warning remain; no dependency
  upgrade was included in this financial change.
- N/A: payment gateway/webhooks, SMS/push integration, new uploads or URL fetching.
- Pending: production deployment, HTTPS/proxy configuration and production verification.
  No Git push or live-site changes performed.

The local DB is at 0033, frontend is rebuilt on port 4550, and private pre-migration
backups plus the stopped previous frontend container are retained. Disposable test
databases were removed after verification; the app database was not deleted.

### Student editing and family details — 2026-10-22

Managers and assigned secretaries can PATCH their institute's student profile:
name, national code, birth date, current grade/major, father/mother contacts,
address, previous school, emergency contact and notes. No school-year field is
accepted. Profile edits do not rewrite past enrollment grade/year, tuition,
course or exam snapshots. Registering another year still uses the existing
year-specific enrollment workflow. The edit dialog explains this distinction.
Personal edits are row-locked and audited by actor and changed field names, not
the private values. National codes stay unique within each institute.

Migration `0034` adds nullable mother name/phone fields; old guardian columns keep
their values and are labelled father in the UI. Both mother fields are optional,
included in lookup/prefill, registration, student details and editing.

PASS: 212 backend tests, Ruff/security rules, mypy, production frontend build,
three browser fixture suites (payment choices, registration, student editing),
and restored PostgreSQL 0033→0034 migration preserving all 32 existing students.
The same five previously documented frontend baseline failures remain; no new
ones appeared. Existing dependency/bundle warnings are not resolved by this feature.

Local rollout completed after the user's explicit localhost request. The private
pre-upgrade backup is retained, application DB is at 0034, and the rebuilt frontend
`azari-accounting-frontend:student-edit-20261022` is active at
`http://localhost:4550`, bound to 127.0.0.1 only. Backend readiness and authenticated
student reads/check-installment previews passed for manager and both secretaries.
No student details or passwords were changed during this verification. Previous
frontend containers remain stopped for recovery. The temporary port-4551 preview
is stopped. The restored `azari_student_edit_test_20261022` verification database
remains for operator cleanup. No live-site changes or Git push were performed.
