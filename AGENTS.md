# Azari project safety rules

Preserve existing user changes. Never commit `.env`, database dumps, real student
records, credentials, or tokens. Frontend `VITE_*` variables are public build data.

## Architecture-specific security

- This application uses FastAPI Bearer JWTs, SQLAlchemy and private PostgreSQL.
  Do not add Supabase `auth.uid()` policies without redesigning identity mapping.
- Every protected API must depend on authentication/permission checks. Authentication
  alone is not ownership: scope school records by workspace AND selected institute.
  Secretaries use their assigned institute only, never a fallback institute.
- Managers can compare their own institutes explicitly, not other managers' data.
  Secretaries must not gain institute aggregate reports, costs or manager-only APIs.
  Out-of-scope resources may return 404; never reveal another tenant's data in errors.
- Only managers create/manage their own secretaries. Credential/role/status changes
  must revoke old sessions. Never expose password hashes or log credentials.
- GET/HEAD/OPTIONS must not initialize schools, seed catalogs, change selection,
  perform predictions, or mutate financial data. Use authenticated writes/startup.
- Compute prices, balances, discounts, cancellation costs and refunds server-side.
  Preserve accounting transactions, locks, Decimal precision and historical snapshots.
- Use ORM/bound SQL values. Do not render user text as raw HTML or execute/import
  user-provided code. ML joblib artifacts are trusted administrator-installed files,
  not uploads: preserve digest/schema/version/path and read-only production checks.
- Browser authentication currently uses explicit Authorization headers, not cookies.
  Do not add cookie authentication without HttpOnly/Secure/SameSite and a CSRF design.
- Use explicit CORS origins; production docs/debug endpoints stay disabled. Trust
  forwarding headers only from explicitly reviewed proxies, never arbitrary clients.
- Login and expensive/sensitive operations need appropriate shared production limits.
  Do not weaken throttling or trust forged X-Forwarded-For to make a test pass.
- Keep CSP script execution strict, sensitive-file/source-map paths blocked, request
  sizes bounded, and API responses non-cacheable. Only built frontend assets are public.
- If adding URL-fetch/upload/payment-webhook features, design SSRF/type-size/storage/
  signature/idempotency defenses before exposing them; do not add unused integrations.

## Verification and delivery

Run backend regression tests, Ruff and configured mypy for relevant changes. Build
the frontend; review existing baseline failures rather than hiding them. Use
`scripts/security_check.py` only against authorized targets. A passing anonymous
scan does not prove tenant isolation: test both reads and writes with two schools,
two secretaries and an unrelated manager. Never use real records for attack tests.

Follow `security/ADAPTED_CHECKLIST.md`. Report PASS, N/A, pending verification and
remaining risks honestly. No Git push, production scan/deployment, account reset,
or database credential rotation without authority for that action.
