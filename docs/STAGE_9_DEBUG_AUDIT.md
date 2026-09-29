# Stage 9 Debug Audit

Audit date: 2026-08-27

Original audit phase: Phase A — investigation only

Original Phase A status: **FAIL**

Remediation date: 2026-08-27

Current status: **PASS WITH ISSUES**

The Phase A investigation proved five HIGH financial-integrity defects: draft invoices entered receivables/dashboard figures, invoice and payment posting accepted semantically invalid or identical accounts, concurrent payments could over-allocate an invoice, and changing the category of a used account retroactively rewrote financial statements. The detailed issue sections below preserve that original evidence. The remediation record immediately below is authoritative for current behavior.

No CRITICAL issue or exposed tracked secret was found. Authentication/RBAC enforcement, normal double-entry posting, ordinary partial/final receipt flows, rollback on tested failures, migration round-tripping, the normal report reconciliation, the four ML pipelines' basic boundaries, and the three-container runtime all passed.

## Stage 9 remediation update

The owner authorized correction of confirmed technical defects while requiring tax behavior to follow only the written specification. `APP_BEHAVIOR_SPECIFICATION.md:204-211` requires an active `TAX_LIABILITY`-role account for a taxed invoice and specifies that an invoice with subtotal 100 and tax 10 increases receivables by 110, revenue by 100, and tax liability by 10. The implementation matches that specification: invoice issuance requires `tax_liability_account_id` when tax is nonzero, credits only `invoice.subtotal` to revenue, and credits `invoice.tax` separately to the tax-liability account. This posting split does not add jurisdiction-specific tax calculation, filing, or settlement behavior.

### Resolved findings

- **A-01 resolved:** receivables/dashboard now include only issued accounting states and exclude DRAFT/CANCELLED invoices.
- **A-02 resolved:** invoice issue requires distinct active ASSET receivable and REVENUE accounts; the frontend filters the choices by those categories.
- **A-03 resolved:** receipt posting requires distinct active ASSET accounts and requires its receivable account to match every allocated invoice's posted debit account.
- **A-04 resolved:** payment and allocated invoice rows are locked with `SELECT ... FOR UPDATE` in deterministic order and revalidated under lock. PostgreSQL replay produced one POSTED and one REJECTED payment, with exactly 100.00 posted allocations against a 100.00 invoice.
- **A-05 resolved:** an account used in any posted journal can no longer change category; historical statement classification cannot be rewritten through that API.
- **A-06/A-07 resolved:** zero-total invoices are rejected, and taxed invoice issue credits revenue for subtotal and a required `TAX_LIABILITY`-role account for tax.
- **V-01/V-02 resolved:** party names are trimmed/nonblank and party emails use validated email syntax.
- **ML-02/ML-03 resolved:** blank classification input is rejected and payment-risk inference requires an issued/partially paid invoice.
- **ML-04 resolved:** segmentation requires an active customer.
- **I-01/I-02 resolved:** `/health` remains process liveness, `/ready` queries PostgreSQL, Compose depends on readiness, and nginx has its own working HTTP healthcheck.
- **I-05 mitigated:** the model bind mount is read-only. Joblib artifacts must still come from a trusted build/release source.
- **S-02 resolved:** the HTTP UI no longer makes an unconditional secure-transport claim.
- **UI-01 resolved:** issue/post forms filter broad account categories, validate distinct receipt accounts, and expose busy states on invoice creation/issue and receipt posting.
- **DOC-01/DOC-02 resolved:** current README/handbook describe top desktop navigation, row locking, readiness, and corrected draft reporting.

### Deliberately unresolved owner decisions

- **UI-02:** the repository cannot legally self-host IRANSans without a licensed WOFF2 asset supplied by the owner. Fallback typography remains.
- Historical `as_of` receivables still use `issue_date`; the specification does not define a separate issuance-timestamp policy.
- Tax treatment follows the explicit split described above; jurisdiction-specific tax rules remain outside scope.

Because the HIGH financial failures are resolved but owner-dependent and production-hardening items remain, the current result is **PASS WITH ISSUES**, not unrestricted production approval.

## Severity definitions

- **CRITICAL** — immediate loss/exposure or a reliably exploitable condition requiring emergency action.
- **HIGH** — confirmed financial-integrity, authorization, or material production-security failure; blocks Stage 9 PASS.
- **MEDIUM** — confirmed defect or meaningful hardening gap that should be fixed before production.
- **LOW** — limited-impact consistency, observability, or maintainability issue.
- **DOCUMENTATION** — source and human documentation disagree, while runtime behavior is otherwise identified.
- **EXPECTED LIMITATION** — deliberately absent or demo-only behavior, not represented as a complete production feature.

## 1. Executive summary

### Outcome by area

| Area | Result | Summary |
|---|---|---|
| Normal accountant workflow | PASS | A 110.00 invoice issued, received in 40.00 and 70.00 installments, settled, and reconciled across trial balance, income, balance sheet, cash flow, and receivables. |
| Adversarial accounting workflow | FAIL | Draft reporting, account semantics, concurrent allocation, and historical account classification are unsafe. |
| Authentication and RBAC | PASS WITH ISSUES | All 53 protected operations passed the anonymous/permissionless/admin matrix; production session controls remain limited. |
| Database and migrations | PASS WITH ISSUES | Upgrade/downgrade/upgrade/drift passed; several financial invariants exist only in service code and are concurrency-sensitive. |
| Transactions and rollback | PASS WITH ISSUES | Tested single-request failures rolled back; simultaneous payment posting violated the invoice allocation invariant. |
| Reporting | FAIL | The normal posted-ledger case reconciled, but draft and retroactive-category cases produce materially incorrect reports. |
| ML | PASS WITH ISSUES | All four synthetic pipelines ran with safe persistence boundaries; validation, lifecycle, and artifact trust gaps remain. |
| Frontend | PASS WITH ISSUES | Persian RTL, top desktop navigation, mobile right drawer, registration, prerequisite notices, and builds pass; several accounting and usability safeguards are absent. |
| API contract | PASS WITH ISSUES | Literal client calls map to implemented routes/schemas; the client cannot infer safe account roles and often hides useful domain errors. |
| Docker runtime | PASS WITH ISSUES | PostgreSQL/backend/frontend run on the documented ports; readiness, headers, secret scoping, restart policies, and frontend health are incomplete. |
| Documentation | PASS WITH ISSUES | Most current architecture/ports are correct, but README/handbook incorrectly describe desktop navigation and some claims overstate concurrency protection. |

### Blocking findings

1. **HIGH A-01:** DRAFT invoices are counted in receivables and dashboard outstanding/overdue data.
2. **HIGH A-02:** Invoice issuance accepts arbitrary active accounts, including the same account on both lines.
3. **HIGH A-03:** Payment posting accepts arbitrary active accounts, including the same account, allowing an invoice to be marked paid without reducing ledger receivables.
4. **HIGH A-04:** Two simultaneous full payments both posted against one invoice: 200.00 allocations against a 100.00 invoice.
5. **HIGH A-05:** An account used by a posted journal can be moved to another category, retroactively moving historical amounts between statements.

## 2. Current architecture

The implementation is a three-service application:

```text
Browser (Persian RTL React/Vite SPA)
  │ http://localhost:4173
  │ JSON/JWT → http://localhost:8100/api/v1
  ▼
FastAPI routes → Pydantic schemas → services/transactions → repositories/SQLAlchemy
  │                                                       │
  ├─ ML registry/inference → trusted joblib artifacts      ▼
  └────────────────────────────────────────────────── PostgreSQL 16
```

- Frontend: React 19, TypeScript, Vite, custom History API router, nginx production image.
- Backend: FastAPI, SQLAlchemy 2, Psycopg, Pydantic settings, Argon2id passwords, JWT access tokens.
- Database: PostgreSQL 16 with Alembic revisions through `20260825_0003`.
- ML: four offline-trained synthetic/demo pipelines; online endpoints load registered artifacts and persist predictions/feedback.
- Runtime mappings: frontend host `4173` → container `80`; backend host `8100` → container `8000`; PostgreSQL container `5432` only.
- Data volumes: named PostgreSQL volume and a writable host bind mount for `ml/models`.

This is primarily a sales invoice/accounts-receivable and management-reporting foundation. It is not a complete ERP.

## 3. Backend audit

### Confirmed strengths

- Routes consistently delegate business mutations to services rather than writing directly in controllers.
- Financial service methods commit or roll back around multi-step mutations.
- Money calculations use `Decimal` and cent precision rather than binary floating point.
- Invoice totals are recalculated by the backend; the browser preview is explicitly approximate.
- Journal posting verifies an open period, active accounts, at least two lines, debit/credit exclusivity, and equality.
- Source-generated invoice/payment journals cannot be reversed through the generic reversal endpoint.
- Domain exceptions are mapped to bounded public responses; unexpected exception details are not deliberately returned.

### Findings

- **HIGH A-02/A-03:** `backend/app/services/accounting.py:352-375` and `:422-458` construct journal lines directly from caller-supplied account IDs. Journal validation checks active/balanced accounts, not semantic account role or distinctness.
- **HIGH A-05:** `AccountUpdate.category_id` is writable (`backend/app/schemas/accounting.py:90-94`), and `update_account` applies it without checking posted use (`backend/app/services/accounting.py:152-176`).
- **MEDIUM V-01:** Party email is a length-limited plain string, not `EmailStr` (`backend/app/schemas/accounting.py:13-14,22-23`). A clearly invalid value was accepted with HTTP 201.
- **MEDIUM V-02:** Most domain names/descriptions use `min_length` without trimming. A whitespace-only party name was accepted with HTTP 201.
- **LOW E-01:** Updating an account to a nonexistent category falls through to a database integrity conflict rather than a resource-specific 404 because the new category is not fetched before assignment.
- **EXPECTED LIMITATION L-01:** There are no draft edit/delete routes for journals, invoices, or payments.

## 4. Database audit

All models and all four revisions were inspected. Primary keys, foreign keys, unique business identifiers, statuses, money precision, timestamps, and the active-model partial uniqueness constraint are represented in migrations. Referential actions are generally conservative; financial history is not cascade-deleted.

### Migration verification

Against the explicitly named disposable database `azari_stage9_audit`:

```text
alembic upgrade head          PASS
alembic downgrade base       PASS
alembic upgrade head         PASS
alembic check                PASS — No new upgrade operations detected
alembic current              20260825_0003 (head)
```

The disposable database was dropped after testing. The normal application database was not mutated by audit scenarios.

### Findings

- **HIGH A-04:** Invoice rows are not locked or version-checked while payments validate and update `amount_paid`. No `SELECT ... FOR UPDATE`, serializable transaction, or optimistic version appears in the payment path.
- **MEDIUM C-01 (suspected):** Financial-period overlap is checked by a normal service query, with no database exclusion constraint or locking strategy. Two simultaneous period creations may both pass. This was identified structurally, not reproduced in the runtime probe.
- **MEDIUM D-01:** `Invoice.amount_paid <= Invoice.total`, allocation-sum equality, and whole-journal balance are not database constraints. Service validation is effective for ordinary single requests but cannot protect every competing transaction or out-of-band writer.
- **LOW D-02:** Timezone-aware timestamps are used for identity/audit/ML events, while accounting dates correctly remain date-only. No timezone drift was observed.
- **EXPECTED LIMITATION L-02:** No database backup/restore automation or retention policy is defined in the repository.

## 5. Accounting/business-logic audit

### Realistic accountant scenario

The disposable scenario created five account types, active accounts, an open 2026 period, customer, supplier, and product. It then created a server-calculated invoice:

```text
3 × 33.33 + 10.01 tax = 110.00
```

After issue, a 40.00 receipt produced PARTIALLY_PAID with 70.00 due; a 70.00 receipt produced PAID with 0.00 due. Duplicate issue and duplicate posting returned 409. The trial balance remained balanced, net income was 110.00, balance sheet balanced, cash flow was 110.00, and receivables became 0.00.

### Confirmed defects

#### HIGH A-01 — draft invoices enter receivables/dashboard

- Current behavior: a 110.00 DRAFT invoice produced receivables `110.00` and dashboard outstanding `110.00`; posted-ledger debit remained `0.00`.
- Intended behavior: `APP_BEHAVIOR_SPECIFICATION.md:107-108,154-156,368-376,414-425` says drafts must not change receivables, reports, or dashboard financial values.
- Evidence: `backend/app/repositories/reporting.py:71-78` filters only `status != "CANCELLED"`.
- Impact: creating drafts makes dashboard numbers grow without ledger activity, matching the reported user symptom.
- Recommended decision: count only invoice states that represent an issued receivable, then define historical issuance semantics (see S-01).

#### HIGH A-02 — invalid invoice posting destinations

- Current behavior: issuance with the same account for receivable and revenue returned HTTP 200 and marked the invoice ISSUED.
- Evidence: caller IDs are used as equal debit/credit lines at `backend/app/services/accounting.py:352-375`; the schemas at `backend/app/schemas/accounting.py:198-200` express UUIDs only.
- Impact: the invoice subledger shows an amount due while the general ledger receives a net-zero entry and no revenue/asset effect.
- Recommended decision: require distinct accounts and define a reliable control-account policy rather than accepting any active account.

#### HIGH A-03 — invalid payment posting destinations

- Current behavior: posting with one identical account for cash and receivable returned HTTP 200, marked the invoice PAID, and left the tested ledger AR balance unchanged at 30.00.
- Evidence: `backend/app/services/accounting.py:422-458` updates invoice balances after posting lines using untyped caller IDs; `PaymentPost` contains UUIDs only (`backend/app/schemas/accounting.py:235-237`).
- Impact: the invoice subledger can say settled while general-ledger receivables remain outstanding.
- Recommended decision: require distinct accounts, validate the debit destination as an approved cash/bank account, and credit the same receivable control account used by the invoice.

#### HIGH A-04 — simultaneous payment over-allocation

- Current behavior: two different DRAFT payments, each allocating 100.00 to the same 100.00 invoice, were posted concurrently. Both returned POSTED. Posted allocations totaled `200.00`, while the invoice stored `amount_paid=100.00` because of a lost update.
- Evidence: balance is read then mutated without locking at `backend/app/services/accounting.py:446-451`.
- Impact: posted journals and allocation history overstate receipts relative to invoice settlement, irreconcilably diverging ledgers.
- Recommended decision: lock all target invoices in deterministic order before validation/update and add a concurrency regression test.

#### HIGH A-05 — retroactive report rewrite through category change

- Current behavior: after posting 77.00 to an asset account, changing that account to an expense category returned HTTP 200; historical expenses increased by 77.00.
- Evidence: account categories are joined at report query time, while category remains mutable (`backend/app/schemas/accounting.py:90-94`, `backend/app/services/accounting.py:152-176`).
- Impact: previously issued statements change without a correcting journal or audit-visible accounting event.
- Recommended decision: prohibit category changes after posted use, or design an explicitly effective-dated reclassification workflow. The former is the minimal fix.

### Other accounting findings

- **RESOLVED A-06:** Zero-total invoice creation is rejected before persistence.
- **RESOLVED A-07:** A taxed invoice requires a `TAX_LIABILITY`-role account; revenue is credited for subtotal and tax is credited separately to that liability account.
- **MEDIUM A-08:** Issue does not revalidate customer/product activity after a draft was created. A later-deactivated master record can remain in a subsequent workflow.
- **LOW A-09:** The generic UI label “payments” covers only incoming customer receipts and can confuse users expecting supplier/outgoing payments.
- **EXPECTED LIMITATION L-03:** Supplier bills, supplier payments, tax engine, inventory accounting, bank reconciliation, payroll, multi-company, and foreign currency are not implemented.

## 6. Authentication/RBAC/security audit

### Results

- All **53 protected operations** tested: anonymous requests returned 401; a valid user with no role returned 403 except `/auth/me`; an ADMIN was never rejected with 401/403.
- Role samples passed: VIEWER read 200/write 403/ML predict 403; ACCOUNTANT accounting write 201/ML manage 403; MANAGER users read 200/accounting write 403.
- Registration returned 201, normalized email case, assigned VIEWER, and stored an Argon2id password hash.
- Normalized login succeeded; wrong password, malformed JWT, and expired JWT returned 401.
- Failed login uses a generic public response and a dummy hash path. No password or token was found in audit records or sampled logs.
- `.env` is ignored and untracked. The tracked scan found only documented placeholder configuration in `.env.example`; no tracked secret was found.
- No unsafe raw SQL, string-built SQL, `eval`, or `dangerouslySetInnerHTML` use was found.

### Findings

- **MEDIUM S-02:** Local Compose is HTTP-only, but `frontend/src/pages/LoginPage.tsx:13` states in Persian that credentials are sent over a secure connection. That statement is false without an external TLS terminator.
- **MEDIUM S-03:** JWTs are stored in `sessionStorage` (`frontend/src/auth/AuthContext.tsx:10-19`) and the nginx response has no CSP. No current raw-HTML injection was found, but any future XSS would expose the token.
- **MEDIUM S-04:** No login rate limiting, account lockout, refresh-token rotation/revocation, MFA, password reset, or email verification exists.
- **MEDIUM S-05:** The backend receives the entire `.env` through Compose `env_file`, broader than its declared settings, increasing accidental secret exposure inside that container.
- **MEDIUM S-06:** Default FastAPI OpenAPI/docs endpoints remain reachable. Production mode does not disable or protect them.
- **LOW S-07:** JWT validation has expiration and required claims but no issuer/audience binding. Secret validation enforces length, not entropy or rotation.
- **LOW S-08:** Audit coverage is strong for major mutations, but category creation and many rejected accounting operations lack dedicated audit events.

## 7. Reporting audit

### Reconciliation results

- Trial balance: debit equaled credit and `balanced=true`.
- Income statement: 110.00 net income after the tested invoice.
- Balance sheet: `balanced=true`; current earnings were incorporated.
- Receivables: 70.00 after partial receipt and 0.00 after final receipt in the workflow.
- Cash flow: 110.00 posted customer cash inflow.
- Revenue/expenses and party history returned persisted data without mutating accounting rows.
- Reversed journal effects were reflected through the separate posted reversing entry rather than by editing history.

### Findings

- **HIGH A-01:** Receivables/dashboard include drafts, as detailed above.
- **HIGH A-05:** Statements use an account's current category, so category edits rewrite historical classification.
- **MEDIUM R-01:** Receivables “as of” uses `issue_date` and current status but stores no `issued_at`. An invoice can be created/backdated and issued later, then appear in an earlier historical snapshot. This is a confirmed model limitation; the exact desired historical policy needs approval.
- **MEDIUM R-02:** Party history is an operational history including records across statuses, while ledger statements use only posted journals. The distinction is reasonable but should be explicit in the UI.
- **EXPECTED LIMITATION L-04:** Payables is liability-account exposure, not a supplier-bill subledger; cash flow covers current posted customer receipts, not a full cash-flow statement.
- **EXPECTED LIMITATION L-05:** Large report/list endpoints have no pagination or export path.

## 8. ML audit

### Verified behavior

- One model for each pipeline was registered and activated in the disposable database: transaction classification, payment-delay risk, cash-flow forecast, and customer segmentation.
- Normal classification, risk, 30-day forecast, and segmentation returned 200.
- Invalid forecast horizon and pre-invoice risk cutoff returned 422.
- Raw transaction description was not persisted; prediction metadata/aggregates were persisted.
- Feedback validation rejected an invalid payload; two valid feedback records appended rather than overwriting history.
- Activation deactivates peers and PostgreSQL enforces at most one active model per pipeline.
- Training scripts are offline. No application startup or request path invokes training.
- Model metadata/schema validation and path containment are implemented; public artifact errors do not expose physical paths.

### Findings

- **HIGH ML-01 (security risk):** Active artifacts are deserialized with `joblib.load` (`ml/common.py:76-90`) from a writable host bind mount. Joblib/pickle must be treated as executable code; host/artifact compromise can become backend code execution.
- **MEDIUM ML-02:** Whitespace-only classification (`"   "`) passed schema validation and inference with HTTP 200 because `min_length=3` does not trim (`backend/app/schemas/ml.py:43-46`).
- **MEDIUM ML-03:** Direct payment-risk API calls accept DRAFT invoices; the frontend filters them, but the backend validates date rather than issued status. The runtime probe returned 200 for a draft.
- **MEDIUM ML-04:** Customer segmentation checks customer role but does not consistently require the party to remain active; frontend filtering is not an authorization/business boundary.
- **MEDIUM ML-05 (suspected):** Unexpected estimator/inference exceptions are not consistently translated to the bounded “prediction unavailable” domain error and may become generic 500 responses. Artifact validation failures are handled; arbitrary estimator failure was not injected.
- **MEDIUM ML-06 (suspected):** The synthetic cash-flow regressor does not enforce nonnegative receipts or intervals. Negative forecasts may be possible for out-of-distribution input.
- **LOW ML-07:** Model cache is process-local. Multi-worker deployments can retain different cache state until each process invalidates/reloads.
- **EXPECTED LIMITATION L-06:** Models are synthetic/demo artifacts. This audit makes no production-accuracy, fairness, or calibration claim.
- **EXPECTED LIMITATION L-07:** There is no automatic retraining, drift monitoring, model approval workflow, or online learning.

## 9. Frontend audit

### Verified behavior

- Document direction/language are Persian RTL; numbers use English digits and tabular number styling.
- Desktop navigation is grouped in the top bar (`frontend/src/layouts/AppLayout.tsx:29-32`); mobile navigation is a right-side drawer.
- Login and public registration routes exist. Registration creates a VIEWER through the backend.
- The previously reported empty required-select problem is handled in invoice, payment, and journal forms with inline Persian prerequisite notices and disabled submission.
- Light/dark preference, Jalali/Gregorian display choice, modal focus handling, Escape close, mobile card layouts, empty/loading/error components, and destructive-action confirmations exist.
- The production bundle, TypeScript, and current frontend tests pass.

### Findings

- **HIGH UI-01:** Invoice issue and payment post forms show every active account in both selects (`frontend/src/pages/TransactionsPages.tsx:30,36`). They allow identical and semantically wrong selections and mirror backend defects A-02/A-03.
- **MEDIUM UI-02:** CSS requests `IRANSans`/`IRANSansX` (`frontend/src/styles.css:2,20`) but no licensed font files or `@font-face` are bundled. Most systems therefore fall back to Vazirmatn/Tahoma/Arial, contrary to the stated IRANSans preference.
- **MEDIUM UI-03:** Most financial submit/action buttons have no busy/disabled state while a request is running, leaving double-click ambiguity. Server uniqueness limits same-record retries, but concurrent distinct payments remain unsafe.
- **MEDIUM UI-04:** The general API error helper replaces many backend domain details with broad Persian messages. Users may not learn which period/account/allocation is invalid.
- **MEDIUM UI-05:** Most successful mutations close/reload without a persistent Persian success message, contrary to the behavior specification's explicit-feedback goal.
- **MEDIUM UI-06:** Public registration silently produces a read-only VIEWER. The registration/onboarding UI does not clearly explain that an administrator must grant operational roles.
- **MEDIUM UI-07 (suspected):** `DateField` retains the last valid ISO value while the user is editing an invalid Jalali value. A form may submit the stale valid date unless invalid visible input is explicitly blocked. This requires browser-level reproduction.
- **LOW UI-08:** “پرداخت‌ها” navigation leads to incoming-receipt behavior; “دریافت‌ها” would better match the implemented operation, subject to owner terminology preference.
- **LOW UI-09:** No true browser E2E/visual/responsive suite exists; current tests render/inspect code paths in Node/SSR style.

## 10. API contract audit

The frontend literal calls were traced through Pydantic inputs, routes, services, repositories, and models. All currently referenced route paths resolve to implemented backend endpoints. IDs are transported as strings/UUIDs, money as decimal-compatible strings, and date inputs as Gregorian ISO dates.

### Findings

- **HIGH API-01:** Account selection contracts carry `category_id` but no explicit posting role such as receivable, revenue, or cash. The issue/post schemas accept generic UUIDs, so neither client nor server can reliably enforce safe control-account intent.
- **MEDIUM API-02:** Frontend permission hiding is correctly backed by API dependencies, but the public registration contract always grants VIEWER and the UI does not communicate that contract clearly.
- **MEDIUM API-03:** ML draft-risk behavior differs: the frontend offers issued/partially paid invoices, while direct backend API accepts draft invoices.
- **MEDIUM API-04:** Backend error `detail` often contains useful domain context, but frontend `friendlyMessage` generally collapses it, reducing actionable feedback.
- **LOW API-05:** Some domain validation failures use a generic 422 or 409 rather than the most specific resource/error representation. No client-breaking field mismatch was found.

## 11. Docker/infrastructure audit

### Runtime verification

```text
docker compose config --quiet      PASS
docker compose up -d --build       PASS
PostgreSQL                         healthy, internal 5432
Backend                            healthy, host 8100 → container 8000
Frontend                           running, host 4173 → container 80
GET backend /api/v1/health         HTTP 200
GET frontend /                     HTTP 200
backend/frontend restart           HTTP 200 after restart
backend container user             uid=999, gid=999 (non-root)
backend container pip check        PASS
sampled current container logs     no ERROR/Traceback/Exception or sensitive-value matches
```

The PostgreSQL named volume remained mounted across container recreation. During Phase A the model directory was a writable bind mount; remediation changed it to read-only.

### Findings

- **MEDIUM I-01:** Backend `/health` is explicitly liveness-only (`backend/app/api/routes/health.py:10-13`). It returned HTTP 200 while PostgreSQL was stopped, yet Compose uses it as backend health and frontend startup dependency (`compose.yaml:32-50`).
- **MEDIUM I-02:** Frontend has no healthcheck; Compose can report it running without verifying nginx/SPA response.
- **MEDIUM I-03:** No restart policies, resource limits, read-only root filesystems, dropped capabilities, or `no-new-privileges` are configured.
- **MEDIUM I-04:** HTTP responses lack CSP, HSTS, X-Frame-Options/frame-ancestors, Referrer-Policy, and Permissions-Policy. HSTS requires actual HTTPS deployment.
- **MEDIUM I-05:** The ML artifact bind mount is writable in the backend container, compounding ML-01.
- **LOW I-06:** Backend image health runs a static endpoint rather than a database readiness probe.
- **EXPECTED LIMITATION L-08:** Compose is a single-host development/runtime definition, not a complete production deployment with TLS, backups, monitoring, and orchestration.

## 12. Error-handling audit

### Confirmed handling

- Wrong login, malformed/expired token: 401 without secret detail.
- Permission denial: 403.
- Missing resources: normally 404.
- Duplicate issue/payment and repeated reversal: 409.
- Supplier-only invoice customer: 422.
- Allocation mismatch, invalid horizon, pre-date ML request, unbalanced/zero journal: 422.
- Closed-period posting: 409; tested journal remained DRAFT.
- Database integrity errors are rolled back and mapped rather than leaking SQL.

### Findings

- **MEDIUM E-02:** Database-unavailable readiness is reported as healthy (I-01).
- **MEDIUM E-03:** Frontend error normalization hides useful safe domain detail (UI-04/API-04).
- **MEDIUM E-04:** There is no global frontend offline/backend-unavailable state beyond per-request generic messages.
- **MEDIUM E-05 (suspected):** Unexpected model estimator exceptions may return a generic server 500 instead of the intended bounded 503.
- **LOW E-06:** Validation response text is primarily backend/technical English; frontend translations are broad rather than field-specific Persian.

## 13. Data-validation audit

### Confirmed protections

- Quantity must be positive with four-decimal precision; prices/tax are nonnegative with two-decimal precision.
- Invoice totals and line totals are calculated server-side.
- Payment amount/allocation values are positive; sums must match; duplicate invoice allocations, cross-customer allocation, settled/invalid invoices, and ordinary over-allocation are rejected.
- Journal debit/credit values are nonnegative and exactly one side must be positive; posting requires a balanced multi-line entry.
- Date ordering and financial-period containment are validated in normal flows.

### Findings

- **MEDIUM V-01:** Party email accepts invalid syntax.
- **MEDIUM V-02:** Whitespace-only party/master-data names are accepted.
- **RESOLVED A-06:** Zero-value invoice drafts are rejected before persistence.
- **MEDIUM ML-02:** Whitespace classification input is accepted.
- **MEDIUM V-03:** Account issue/post schemas validate UUID shape only, not business posting role or distinctness.
- **LOW V-04:** Update schemas can produce database-level generic conflicts for invalid foreign keys instead of validating referenced resources first.

## 14. Transaction/rollback audit

### Multi-step operations inspected

- Invoice issue: create journal + lines, post, link invoice, change status, audit, commit.
- Payment post: post journal + lines, update each invoice, link payment, change status, audit, commit.
- Journal post/reversal: validate, create or mutate journal state, audit, commit.
- Model activation: deactivate peers, activate target, audit, commit.

### Results

- A deliberately forced payment-post failure returned 409; payment remained DRAFT and no generated journal leaked.
- Unbalanced journal post returned 422 and remained DRAFT.
- Closed-period post returned 409 and remained DRAFT.
- Duplicate issue/post/reversal did not create a second same-source effect.
- Existing tests also cover service rollback paths.
- **HIGH A-04:** Atomic rollback does not solve concurrent read/validate/write. Both independent payment transactions committed, violating the aggregate allocation invariant.
- **LOW T-01:** No general request idempotency key exists. Unique document references/status prevent many retries, while append-only feedback intentionally accepts repeats.

## 15. Production-readiness audit

The application is suitable for controlled development/demo use, not production financial use yet.

### Blocking production gaps

- Resolve A-01 through A-05 and add regression/concurrency tests.
- Establish TLS and truthful transport messaging.
- Make model artifacts immutable/trusted at runtime.
- Add real readiness, frontend health, backups, monitoring, log policy, secret scoping/rotation, and deployment hardening.
- Add browser E2E tests for the main Persian accountant journey and accessibility/responsive behavior.
- Define account-control semantics and historical reporting policy.

### Dependency/tooling observations

- Python environment `pip check`: PASS.
- Backend container `pip check`: PASS.
- Frontend production dependency audit: 0 vulnerabilities.
- Current warnings: 5,229 joblib/NumPy synthetic-model warnings plus Starlette/httpx deprecation and Windows test-cache permission warnings. They do not fail tests but obscure useful signal and should be reduced.

## 16. Documentation consistency audit

- **DOCUMENTATION DOC-01:** `README.md:93` and `HOW_THE_PROJECT_WORKS.md:566,1100` say desktop navigation uses a sidebar. Actual code uses grouped top navigation (`frontend/src/layouts/AppLayout.tsx:29-32`), matching `PROJECT_ANALYSIS.md:297` and the Stage 9 target.
- **DOCUMENTATION DOC-02:** `HOW_THE_PROJECT_WORKS.md:400,1043` overstates concurrent-payment protection. Status/unique constraints protect repeated posting of the same payment, but the probe proved two distinct payments can over-allocate one invoice.
- **DOCUMENTATION DOC-03:** `docs/DATABASE.md` describes receivable/payment history but does not clearly state the confirmed draft-inclusion and historical-issuance limitations.
- **DOCUMENTATION DOC-04:** Stage documents intentionally retain old ports, test counts, and then-current statuses as historical verification records. They should not be rewritten as if they were current results.
- **DOCUMENTATION DOC-05:** The handbook correctly calls out draft receivables, unbundled IRANSans, Viewer registration, and missing account-type validation, but its final “accounting workflow coverage PASS” language is too broad given the proven concurrency and reclassification failures.
- Current operational ports in README, Compose, `.env.example`, API defaults, and setup documentation are otherwise consistent: frontend 4173 and backend 8100.

## 17. Known bugs

| ID | Severity | Confirmed bug |
|---|---|---|
| A-01 | HIGH | Draft invoice enters receivables/dashboard before issue. |
| A-02 | HIGH | Same/wrong account invoice issue succeeds and creates invalid economic effect. |
| A-03 | HIGH | Same/wrong account payment post can settle subledger without reducing GL receivables. |
| A-04 | HIGH | Concurrent full payments both post and over-allocate one invoice. |
| A-05 | HIGH | Category update of used account rewrites historical statements. |
| A-06 | RESOLVED | Zero invoice creation is rejected before persistence. |
| V-01 | MEDIUM | Invalid party email accepted. |
| V-02 | MEDIUM | Whitespace-only party/master names accepted. |
| ML-02 | MEDIUM | Whitespace-only classification accepted. |
| ML-03 | MEDIUM | Direct API predicts delay risk for draft invoice. |
| I-01 | MEDIUM | Health reports 200 when required database is unavailable. |
| S-02 | MEDIUM | Login UI claims a secure connection in an HTTP-only local runtime. |
| UI-02 | MEDIUM | IRANSans is named but not provided, so it generally is not rendered. |

## 18. Suspected bugs

These require targeted reproduction before being called confirmed:

- **MEDIUM C-01:** simultaneous financial-period creation may bypass overlap validation.
- **MEDIUM UI-07:** invalid/partial Jalali input may submit the previous valid ISO date.
- **MEDIUM ML-05:** arbitrary estimator exception may become 500 rather than bounded ML-unavailable response.
- **MEDIUM ML-06:** cash-flow model may emit negative values/intervals for out-of-distribution inputs.
- **LOW SB-01:** account hierarchy changes are cycle-checked in application code, but concurrent parent changes may create a cycle without database support.

## 19. Risks

### Accounting risks

- Financial dashboard and receivable reports can disagree with the posted ledger.
- User-selected accounts can produce economically meaningless but technically balanced entries.
- Payment concurrency can create posted cash/AR journals exceeding invoice allocations.
- Historical reports can change after master-data edits without correcting entries.
- Historical “as of” receivables lack a reliable issuance timestamp.

### Security risks

- Writable pickle/joblib artifacts are an executable supply-chain boundary.
- No TLS/security headers/rate limiting/revocation/production secret isolation are provided by the repository runtime.
- Browser token storage raises impact of any future XSS.

### ML risks

- Synthetic artifacts have no real-world accuracy guarantee.
- Direct API validation is looser than UI filtering for risk/segmentation.
- Process-local cache and writable artifacts complicate multi-worker integrity.

### Frontend usability risks

- Unsafe financial account choices are presented without filtering/guidance.
- Generic errors and absent success/busy states create uncertainty and repeated clicks for nontechnical users.
- Unclear Viewer onboarding can make registration appear broken.
- The requested Persian font is usually not actually present.

### Infrastructure risks

- Liveness is mistaken for readiness.
- No frontend healthcheck, restart policy, resource controls, backup policy, or production observability.
- Security headers and TLS are absent.

## 20. Recommended fixes

No fixes are applied in this Phase A document. Recommended order:

1. **Owner decision:** confirm draft and historical receivable semantics, then fix A-01/R-01 and add report/dashboard regression tests.
2. **Owner decision:** define invoice/payment control-account rules; minimally enforce distinct accounts and category/role compatibility in backend and filtered UI (A-02/A-03/UI-01).
3. Lock invoice rows in deterministic order during payment posting, recheck allocations under lock, and add a real concurrent-post regression (A-04).
4. Forbid category changes once an account participates in a posted journal, unless an effective-dated reclassification design is explicitly chosen (A-05).
5. **Implemented in Phase B:** reject zero invoices and split tax from revenue into a required tax-liability posting (A-06/A-07).
6. Normalize/trim human text, use `EmailStr` for party emails if email is intended to be syntactic, and reject blank ML input (V-01/V-02/ML-02).
7. Require an issued/partially-paid invoice for payment-risk inference and active customers for segmentation (ML-03/ML-04).
8. Separate `/health` liveness from database-backed readiness; add a frontend healthcheck (I-01/I-02).
9. Make artifacts read-only and deploy only authenticated, checksummed/trusted artifacts; document pickle risk (ML-01).
10. Add submit busy states, targeted Persian errors/success notices, and explicit Viewer onboarding (UI-03 through UI-06).
11. Add TLS termination, security headers, rate limiting, secret scoping, restart/resource policies, backups, monitoring, and production runbooks.
12. Reproduce suspected period, Jalali, and estimator/forecast cases before fixing them.
13. Correct current documentation only after semantics and fixes are approved; preserve historical stage records.

### Business-semantics decisions required before Phase B/C

1. Should receivables/dashboard include exactly `ISSUED`, `PARTIALLY_PAID`, and non-settled `PAID` history, and should historical `as_of` exclude invoices not yet issued at that moment? Supporting the latter reliably may require an issuance timestamp or audit-derived policy.
2. What defines a valid AR, revenue, and cash/bank posting account: broad account category, a configured control-account designation, or fixed organization settings? Category-only validation is better than current behavior but still allows the wrong asset account.
3. Should a used account's category be permanently immutable, or should category movement require a dated accounting reclassification workflow?
4. **Decided in Phase B:** zero-total invoices are prohibited, and invoice tax credits a distinct `TAX_LIABILITY`-role account rather than revenue.
5. Should reversal into a closed historical period remain forbidden, or should reversal post into the current open period with a reference to the source?

## 21. Items that should NOT be changed

- Do not start Stage 10 or add supplier bills, payroll, inventory, bank reconciliation, tax engine, new ML pipelines, notifications, or major analytics.
- Do not redesign the established Persian RTL, green, light-default, light/dark, top-desktop/right-mobile navigation direction.
- Do not replace PostgreSQL/SQLAlchemy/FastAPI/React or rewrite the architecture to address localized defects.
- Do not edit old migrations merely to make current tests pass; use an additive migration only if an approved fix truly needs schema support.
- Do not calculate authoritative invoice totals in the browser or replace `Decimal` financial calculations with float.
- Do not weaken journal balance, period, activity, state-transition, unique-reference, permission, or audit protections.
- Do not train models at startup or during request handling; do not claim production ML accuracy.
- Do not persist raw classification descriptions or expose artifact filesystem paths/secrets.
- Do not replace Docker internal service addresses with host `localhost`; keep current port mappings unless the host reservation changes.
- Do not rewrite historical stage failure/port/test records as current facts.
- Do not modify or commit `.env`, user credentials, editor temporary files, or unrelated working-tree changes.

## Final issue summary

### Critical issues

None confirmed.

### High issues

A-01 through A-05 and ML-01 (production artifact supply-chain risk).

### Medium issues

A-08, C-01, D-01, E-02 through E-05, I-01 through I-05, ML-02 through ML-06, R-01/R-02, S-02 through S-06, UI-02 through UI-07, and V-01 through V-03. A-06 and A-07 were resolved in Phase B.

### Low issues

A-09, D-02, E-01/E-06, I-06, ML-07, S-07/S-08, T-01, UI-08/UI-09, V-04, and SB-01.

### Documentation issues

DOC-01 through DOC-05.

### Expected limitations

L-01 through L-08: narrow draft mutation surface, no repository backup automation, accounts-receivable-only workflow, limited payable/cash-flow meaning, no pagination/export, synthetic ML without retraining, and development-oriented Compose.

## Changes made

- Fixed draft receivable/dashboard filtering, posting-account validation, invoice-receivable matching, concurrent payment locking, and historical category mutation.
- Tightened party and ML validation and active-customer/invoice eligibility.
- Added database-backed readiness, frontend HTTP health, and a read-only ML model bind mount.
- Filtered financial posting choices by account category, added targeted Persian guidance, busy states, and truthful login transport wording.
- Added backend/frontend regression coverage and updated current documentation. No database schema or migration changed.
- Temporary verification scripts and the exact disposable databases `azari_stage9_audit` and `azari_stage9_concurrency` were removed after use.

## Verification

```text
Backend + ML tests
  .venv/Scripts/python.exe -m pytest backend/tests ml/tests --cov=backend.app --cov=ml --cov-report=term
  PASS — 76 passed; 95% combined coverage; 5,231 warnings

Ruff
  .venv/Scripts/python.exe -m ruff check backend ml scripts
  PASS

Strict mypy
  .venv/Scripts/python.exe -m mypy --config-file backend/pyproject.toml backend ml scripts
  PASS — 91 source files

Frontend tests
  frontend/test.cmd
  PASS — 19 tests

TypeScript
  npm run typecheck
  PASS

Frontend production build
  npm run build
  PASS — 47 modules; CSS 24.03 kB; JS 292.27 kB

Dependency checks
  host pip check                         PASS
  backend-container pip check            PASS
  npm audit --omit=dev                    PASS — 0 vulnerabilities

Migrations on disposable PostgreSQL DB
  upgrade → downgrade base → upgrade     PASS
  alembic check                           PASS — no drift
  current                                 20260825_0003 (head)

Disposable black-box/integration probe
  protected endpoint matrix               PASS — 53 operations
  normal invoice/payment/report flow      PASS
  duplicate/invalid/closed/rollback flow  PASS
  ML basic boundaries                     PASS WITH ISSUES
  original adversarial accounting probe   FAIL — A-01 through A-05 reproduced
  remediation regression suite            PASS
  PostgreSQL concurrent-payment replay     PASS — POSTED, REJECTED; 100.00 allocated

Docker
  docker compose config --quiet           PASS
  docker compose up -d --build             PASS
  PostgreSQL                               healthy
  backend liveness/readiness                HTTP 200 on host 8100
  frontend                                 HTTP 200 and healthy on host 4173
  restart check                            PASS
  DB-unavailable readiness check           PASS — liveness 200, readiness 500
```

## Remaining risks and disposition

Stage 9 was **PASS WITH ISSUES** at this pre-Phase-B checkpoint. The confirmed HIGH accounting defects were resolved and covered by regression tests, including a PostgreSQL concurrency replay. Stage 10 had not started. At this checkpoint, zero-total and tax decisions were still pending; Phase B below records the later decisions and implementation: zero-total invoices are rejected, revenue receives subtotal only, and tax posts separately to a required `TAX_LIABILITY`-role account.

## Phase B implementation — 2026-08-27

This section records the later owner decisions and implementation results. The
Phase A findings above remain as historical evidence and are not rewritten.

### Resolved HIGH accounting and security defects

- Draft invoices remain operational records only and are excluded from ledger,
  receivable, revenue, cash-flow, report, and dashboard financial totals.
- Accounts now have explicit `GENERAL`, `CASH`, `RECEIVABLE`, `REVENUE`, and
  `TAX_LIABILITY` posting roles. Invoice/payment posting requires the exact
  semantic role; broad account category is insufficient.
- Account category and posting role are immutable after posted journal use.
- Zero-total invoices are rejected before persistence.
- Taxed invoice issue debits receivables for total, credits revenue for subtotal,
  and credits tax to an explicit tax-liability account. No jurisdiction-specific
  tax calculation, filing, or settlement semantics were invented.
- Generic reversal remains a new immutable journal and is rejected atomically if
  its period is closed. The current endpoint does not invent a new reversal date
  or period.
- Payment and invoice rows are locked and allocations are revalidated under the
  transaction. A real PostgreSQL two-payment race produced exactly one `POSTED`
  and one `REJECTED` result.
- Model registration now inspects inert metadata and pins a SHA-256 digest without
  deserializing joblib. Activation/loading rejects missing or changed digests;
  production additionally rejects artifacts writable by the backend process.
  Artifact paths are not returned in errors or API responses.

### Migration

Additive migration `20260827_0004` adds `accounts.posting_role` and
`ml_model_versions.artifact_digest`. Existing accounts default to `GENERAL`
rather than receiving guessed accounting semantics. Existing active model rows
are deactivated and require an explicit administrator activation to pin and
validate their artifacts.

### Final Phase B verification

```text
Backend + ML tests                 PASS — 83 tests; 95% combined coverage
Accounting-focused regression      PASS — 25 tests
ML security-focused regression     PASS — 14 tests
Frontend tests                     PASS — 19 tests
TypeScript                         PASS
Frontend production build          PASS — 47 modules
Ruff (project-scoped)              PASS
Strict mypy                        PASS — 82 source files
PostgreSQL migration current       PASS — 20260827_0004 (head)
Alembic drift check                PASS — no new upgrade operations
PostgreSQL tax/concurrency probe   PASS — POSTED, REJECTED
docker compose config              PASS
docker compose up -d --build       PASS
PostgreSQL                         healthy; accepting connections
Backend liveness/readiness         HTTP 200 / HTTP 200 on host 8100
Frontend                           healthy; HTTP 200 on host 4173
Backend container pip check        PASS
git diff --check                   PASS
```

The exact disposable database `azari_stage9_phase_b_test` was removed after the
PostgreSQL probe. It contained verification data only.

### Status and remaining issues

Stage 9 Phase B is **PASS**, and the defined Stage 9 HIGH-remediation scope has
passed full regression, PostgreSQL accounting, migration, and Docker checks.
Stage 10 has not started. Remaining documented limitations include the absence
of a jurisdiction-specific tax engine, no API for selecting a new open
date/period when reversing a journal whose original period is closed, no
historical invoice issuance timestamp, synthetic ML fitness limitations,
unbundled licensed IRANSans assets, and the medium/low infrastructure and product
risks retained in the Phase A audit.
