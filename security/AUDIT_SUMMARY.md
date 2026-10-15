# Azari adapted security audit — 2026-10-15

## Outcome and scope

Applied the relevant ideas from [vibe-check](https://github.com/benavlabs/vibe-check)
to this existing school application. No third-party scanner, generic Supabase
policies, replacement authentication system or unused payment/upload integration
was installed. No Git push/commit, live-server scan/deployment, password reset of
real/demo accounts, `.env` edit, or production database permission change occurred.
Earlier uncommitted application changes were preserved.

This is a targeted local hardening/verification pass, not a certification or a
complete manual browser/production penetration test. The
[17-category mapping](ADAPTED_CHECKLIST.md) records applicability and remaining checks.

## Changes made in this pass

- Added project-specific persistent rules in `AGENTS.md`: institute/workspace
  ownership, secretary restrictions, financial integrity, Bearer authentication,
  safe GETs, trusted artifacts and release verification.
- Removed school/institute setup and exam catalog seeding from GET paths.
  Setup now uses authenticated write flows or the explicit post-migration CLI.
  Existing prices, archives and student financial snapshots are not rewritten.
- Added a separate throttle to manager-triggered secretary password resets,
  in addition to ownership checks, permission checks and session revocation.
- Disabled credentialed CORS: browser cookies do not carry identity in this app.
  Added API CSP `form-action 'none'` while keeping the existing strict script CSP.
- Explicitly blocked dotfiles, backups/database dumps, backend source and source
  maps in both Nginx deployment variants; directory listing disabled.
  These are defense-in-depth changes, not evidence that secrets were previously leaked.
- Explicitly disabled Vite production source maps. Kept `npm ci` and its existing
  exact lockfile; did not mechanically rewrite every package version declaration.
- Added exact Python production constraints based on the existing reviewed Linux
  runtime, wired into both Dockerfiles and CI. All 46 constrained package versions
  match the running backend. These are version constraints, not wheel hashes.
- Added an app-specific bounded anonymous HTTP scanner and an exhaustive FastAPI
  authentication-dependency inventory, each failing rather than silently passing
  when its checks cannot run.
- Added regression tests for every protected API operation, GET write detection,
  cross-origin cookie-only requests, cross-school direct IDs/read/write attempts,
  foreign course selection, password-reset throttling, and scanner behavior.
- Added an early test-suite guard: non-memory database URLs are refused before
  importing application/database modules, so unit fixtures cannot drop a real schema.

## Verification results

| Check | Result |
| --- | --- |
| API authentication inventory | 116 operations: 112 protected; four intentionally public (health, readiness, registration, login). Every protected operation tested without a token. |
| Local HTTP scan through Nginx | 34 PASS, 0 FAIL, 1 WARN (localhost is HTTP, not HTTPS). Checks actual HTML/JS headers, `.env`/Git/backup/source/map paths, protected APIs, CORS and cache policy. |
| Tenant-isolation regression | Second secretary, manager viewing the other school, and unrelated manager denied direct student/payment access and foreign-course enrollment. Original payment and student counts unchanged. |
| Password reset regression | Limit reached returns 429 and Retry-After; login uses a separate throttle namespace. Test fixtures only. |
| Backend suite | Release verification: all 182 tests passed, including the external-database safety guard. |
| Strict mypy | Pass, 61 application source files. |
| Ruff normal and security rules | Pass for application and relevant new tests/scripts. |
| Frontend Docker build | Pass; TypeScript and Vite production build included. |
| Nginx syntax | Pass for frontend config and rendered single-container deployment template. |
| Compose configuration | Renders successfully; no credentials printed. |
| Redacted source secret scans | Updated backend application and scripts: no findings. Prior history/frontend scan results remain in the earlier report. |
| Runtime dependencies | All 46 exact constraints match the existing Linux runtime. Clean constrained installation is still pending the package-network fix. |

The local frontend was rebuilt and replaced at `http://localhost:4550`.
The backend was restarted with its read-only updated source mount and existing
installed dependencies. Its readiness check must pass before running HTTP checks;
an initial scan during restart returned 502 and was rerun after startup completed.
The previous frontend container remains stopped for recovery.
Authenticated runtime checks also passed: manager student/course/cost access 200,
secretary student/course access 200, and secretary cost access 403. Tokens were
minted internally and not printed; remembered account passwords were not verified
or changed.

## Remaining risks / incomplete deployment checks

- `inkcollection.ir` was neither scanned nor changed in this pass. Host/CDN/TLS,
  deployed headers, debug exposure and proxy/IP behavior remain unverified.
- A clean constrained backend Docker build/pip-audit is still required on a
  working package network; earlier attempts failed resolving Python's download host.
  The local running backend is **not** proof of a fresh production image build.
- The local PostgreSQL application role is still a superuser. Do not deploy that
  privilege model unchanged; provision/review production least-privilege access.
  Supabase browser grants/RLS, if applicable, require separate deployment review.
- Browser tokens remain in session storage, hence accessible to JavaScript.
  No cookie migration was performed; stored/reflected XSS still needs browser testing.
- Expensive ML abuse budgets, centralized alerts/log retention, OS/container image
  scanning, hash-verified dependency artifacts, backup/restore drills and production
  end-to-end role tests are not declared complete.
- The frontend's five previously reproduced unrelated test failures were not hidden
  or fixed incidentally. The production build passes; the full frontend suite is
  not claimed green. Existing SQLAlchemy cycle/deprecation warnings remain.

## Operator commands

Use the commands in [ADAPTED_CHECKLIST.md](ADAPTED_CHECKLIST.md). For a public-server
scan, obtain authorization and use its canonical HTTPS origin without the
`--development` flag. Review warnings and failures individually; do not turn a
security check off merely to obtain a green result.

Related historical evidence: [previous hardening report](../docs/SECURITY_HARDENING_REPORT.md).
