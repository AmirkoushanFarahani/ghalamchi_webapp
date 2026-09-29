# Stage 3 — Accounting Vertical Slice

Implementation date: 2026-08-18

## Domain and database

Migration `cd6670d77e70` adds eleven normalized tables: `parties`, `products`,
`account_categories`, `accounts`, `financial_periods`, `journal_entries`,
`journal_lines`, `invoices`, `invoice_items`, `payments`, and
`payment_allocations`. UUIDs identify records, timestamps are timezone-aware,
money is `NUMERIC(18,2)`, and quantity is `NUMERIC(18,4)`. A party can be both a
customer and supplier. Accounts support parent links with self/cycle guards.

## Accounting invariants and lifecycle

All posting flows use `AccountingService`. A POSTED journal requires at least
two lines, exactly one positive debit/credit side per line, equal debit and
credit totals, active accounts, an OPEN period, and a date inside that period.
Drafts may exist before posting. Posted journals have no update/delete service
or API and corrections use a new balanced reversal linked to the unchanged
original. Posting failures roll back the full transaction.

Period dates must be ordered and periods cannot overlap through the service.
Closing a period blocks later posting. Row-level date, status, amount, quantity,
uniqueness, debit/credit, and foreign-key invariants also have named database
constraints.

## Invoices and payments

Invoice item subtotals/totals and invoice totals are calculated on the backend;
client totals/statuses are not accepted. Draft invoices do not touch the
ledger. Issuance atomically debits the selected receivable account and credits
the selected revenue account.

Payments require positive allocations whose sum equals the payment and cannot
exceed any target invoice balance. Posting atomically debits the selected cash
account, credits receivables, applies allocations, and derives PARTIALLY_PAID or
PAID. Cancelled or otherwise invalid invoices reject allocations. Failed issue
or payment posting leaves no partial journal or state change.

## Permissions and audit

Stage 3 adds read/write/post/issue/manage permissions for parties, products,
accounts, periods, journals, invoices, and payments. ADMIN receives all;
ACCOUNTANT receives operational permissions; MANAGER and VIEWER receive read
permissions. Public registration remains VIEWER and unchanged. Every important
accounting mutation records an append-oriented audit event without credentials,
tokens, secrets, or password material.

## API

Versioned `/api/v1` endpoints cover party/product/account CRUD, account
categories, periods and closing, journals and post/reverse, invoices and issue,
and payments and post. Pydantic schemas serialize responses; ORM models are not
returned directly as contracts. Missing authentication returns 401, missing
permission 403, missing resources 404, conflicts 409, and domain validation 422.

## Verification

- Backend: 42 tests passed; 93% total application coverage and 93% focused
  accounting-service coverage.
- Accounting: balance, line rules, active accounts, closed periods,
  immutability surface, reversal, invoice totals/issue, partial/full payment,
  over-allocation, cancelled invoice, and rollback tests passed.
- Security: API 401/403, Stage 3 permission bootstrap, and audit tests passed.
- Strict mypy: no issues in 47 source files.
- Ruff format/check: passed.
- Frontend production build: passed; 30 modules transformed.
- PostgreSQL 16: upgrade, downgrade to Stage 2, upgrade, schema/NUMERIC checks,
  real invoice/payment/ledger workflow, and Alembic no-drift check passed.
- Disposable `azari_stage3_test` database was removed after verification.
- Compose: configuration rendered and full three-service runtime rebuilt;
  PostgreSQL/backend healthy, backend HTTP 200 on host 8100, frontend HTTP 200
  on host 4173.
- `git diff --check`: passed.

## Known limitations

- Stage 3 supports receivable invoices/customer payments only; supplier bills
  and payables are later work.
- Tax is a per-line amount credited with revenue in this minimal slice; a
  separate tax-liability workflow is not yet implemented.
- Overdue presentation is derived by consumers from due date and outstanding
  balance; no scheduler persists an OVERDUE status.
- Posted corrections support full reversals, not partial reversal workflows.
- Pagination and advanced search are intentionally deferred.

## Result

Stage 3 is **PASS**. Stage 4 has not started.
