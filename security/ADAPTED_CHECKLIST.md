# Azari security checklist — adapted, not copied

Inspired by [Benav Labs vibe-check](https://github.com/benavlabs/vibe-check).
The controls below fit FastAPI + React + private PostgreSQL with Bearer JWTs,
manager-owned workspaces and separately scoped institutes. A checklist is not a
penetration test. Never attack or mutate real student records to verify a control.

## Applicability and evidence

| # | Category | Azari adaptation / evidence | Remaining verification |
| --- | --- | --- | --- |
| 1 | Secrets exposure | `.env` and backups ignored; prior redacted Gitleaks scans; Nginx explicitly blocks dotfiles, dumps, source and backup paths. | Scan release history/current source and production responses before each release. |
| 2 | Database access | Private PostgreSQL behind FastAPI; both workspace and institute filters are required. Read-only database exposure checker exists. | Production least-privilege DB role/network and any Supabase browser-role grants. Do not invent `auth.uid()` policies for these app UUIDs. |
| 3 | Authentication | Exhaustive route inventory follows authentication dependencies, including FastAPI's lazy included routers; tests replay every protected method without a token and expect 401. | Re-run inventory/tests whenever routes change. Health/readiness/login/register are the only public API exceptions. |
| 4 | Object authorization | Manager, two institutes/secretaries and unrelated manager tests exercise direct student/payment IDs, injected foreign course IDs and user-directory scoping. 404 is a valid non-disclosing denial. | Extend write/read tests for every new resource; do not equate an anonymous scan with isolation proof. |
| 5 | Frontend exposure | `build.sourcemap: false`, npm's committed lockfile, Nginx blocks `.map`; scanner checks actual bundle/map and sensitive responses without logging bodies. | Test the production CDN and deployed assets, not just local source. Frontend code/route names are not secrets. |
| 6 | SSRF | No user-supplied URL-fetch feature found in runtime app/ML/frontend search. CLI security scanner is an authorized operator tool, not a public endpoint. | N/A until URL import/webhook-test/proxy features are introduced. Then require DNS/redirect/private-address defenses. |
| 7 | CSRF / safe methods | Identity comes only from explicit Bearer headers; cookies do not authenticate. Cross-origin form/preflight regression tests added; CORS credentials disabled. School GETs no longer provision institutes or seed exams. | HttpOnly-cookie migration, if chosen later, must include CSRF design. XSS/token theft remains a separate risk. |
| 8 | Headers | Existing strict script CSP and global headers retained, API form-action tightened; scanner checks HTML and an actual JS asset. | HTTPS/HSTS, TLS termination, subdomain safety and production host/CDN overrides. No HSTS preload enrollment performed. |
| 9 | CORS | Exact configured origins; arbitrary origins rejected. Explicit Bearer header does not require credentialed cookies. | Production allowlist and trusted proxy path; an allowed origin is not authorization. |
| 10 | Rate limiting | Shared atomic PostgreSQL auth counters; manager-only secretary password reset now throttled before mutation. Existing concurrency test checks allowed/blocked counts. | Accurate client IPs behind reviewed proxies, abuse/availability budgets for expensive ML endpoints. No global proxy trust enabled. |
| 11 | SQL injection | Runtime query search found ORM/bound statements, not interpolated request SQL. Identifier interpolation in admin database-hardening CLI uses quoted fixed metadata identifiers. | Review future raw SQL and use a restricted DB role; do not run destructive SQL payloads against production. |
| 12 | XSS | React renders user text; no `dangerouslySetInnerHTML`, `innerHTML`, or `v-html` sink found in application source search. Strict script CSP retained. | Browser-based stored/reflected XSS verification and future rich-text features. Session-storage tokens remain JavaScript-accessible. |
| 13 | Payment webhooks | School payments are manual records, not Stripe/gateway callbacks. Preserve server-computed amounts and transactional balance checks. | Gateway webhook signatures, replay/idempotency and gateway-status validation only if such an integration is added. |
| 14 | Uploads / artifacts | No public upload endpoint found. Spreadsheet imports are operator tools; joblib artifacts remain administrator-trusted, digest/schema/path checked and read-only in production. | If uploads are added, enforce size/type/storage/access controls first. Digest validation does not make untrusted pickle safe. |
| 15 | Errors / debug | Production generic errors/docs disabled; anonymous scanner distinguishes SPA fallback from real debug/docs contents. Security logs exclude bodies/tokens/query strings. | Actual server `APP_ENV`, routing and logging config; external alert delivery and safe diagnostic retention. |
| 16 | Password hashing | Argon2id and bounded request passwords; existing verification/reset/revoked-session tests. | Protect credentials/backups; do not reset demo users or rotate live credentials as an incidental test. |
| 17 | Dependencies | npm ci + package-lock; reviewed exact Python runtime constraints added to both Docker builds/CI; prior runtime advisory scan clean. | Full clean constrained build/pip-audit on working package network, hash-locked artifacts and OS-image scanning. Constraints are not a hash-verified lock. |

## Repeatable checks

Run from the project root, with the normal test environment available:

The unit suite refuses any pre-set external `DATABASE_URL` before importing the
database engine. Use an in-memory SQLite URL for this suite and the dedicated,
isolated PostgreSQL scripts for concurrency/database-specific verification.

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\ruff.exe check backend/app
.venv\Scripts\ruff.exe check --select S backend/app
.venv\Scripts\mypy.exe --config-file backend/pyproject.toml backend/app
.venv\Scripts\python.exe -m scripts.security_routes
.venv\Scripts\python.exe scripts/security_check.py http://localhost:4550 --development --json
npm --prefix frontend audit --audit-level=moderate
npm --prefix frontend run build
```

The route inventory imports configuration but does not print secrets or query the
database. The external scanner makes bounded unauthenticated GET requests only,
does not follow redirects, does not attempt login, and never records response bodies.
It exits nonzero on failures; warnings (e.g. HTTP-only localhost) are not passes.
It checks the root-origin deployment used by this app, not arbitrary mounted prefixes.

`--development` allows local development docs only. Do not use that flag to claim
production is safe. Production scanning must be explicitly authorized; no live
scan of inkcollection.ir was performed during this change.

## Initialization change

School/institute and missing default catalog initialization now happens during
education manager registration/successful login, explicit institute creation, or
the explicit post-migration initializer
`python -m backend.scripts.initialize_school_workspaces`. Reads never silently
create a school or reinstall exams. RBAC bootstrap remains usable during older
staged migrations and does not query the latest school schema prematurely.
Initialization preserves existing catalog edits/deletions and enrollment snapshots.
Startup may perform setup writes; it must use a controlled server DB connection.

## Release gate

Before deployment, verify: clean constrained backend build, all regression tests,
Nginx syntax, local HTTP checks, private DB backup/restore plan, production secrets,
least-privilege DB role, TLS and proxy trust. After an authorized deployment, rerun
the scanner on the public HTTPS origin and manually verify two-school access.
See [AUDIT_SUMMARY.md](AUDIT_SUMMARY.md) for this run's results and limitations.
