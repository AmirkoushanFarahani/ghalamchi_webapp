# Security hardening — 15 October 2026

This records the first pass. The subsequent architecture-adapted vibe-check pass
and current verification results are documented in
[security/AUDIT_SUMMARY.md](../security/AUDIT_SUMMARY.md).

Scope: local application and deployment source configuration. No Git commit/push,
live-server change, credential reset, or production deployment was performed.
Existing unrelated working-tree changes were preserved.

## Article checklist and implementation

| Area | Implemented / verified |
| --- | --- |
| Secrets | Gitleaks history scan: 46 commits, no findings. Current backend application, frontend source and scripts scanned with redacted output. Private `.env` unchanged; no database dump or credentials added to Git. |
| Database exposure | Added read-only `python -m backend.scripts.security_database`. Local PostgreSQL has no Supabase browser roles or direct browser grants. API tenant isolation remains essential. |
| Backend validation | 1 MiB request limit, including chunked requests; enrollment collection limits; production rejects placeholder JWT secrets and wildcard CORS. |
| Authorization | Invalid/missing/inactive secretary institute assignments now fail closed instead of selecting another institute. Manager user directory scoped to their own workspace. Shared ML registry management restricted to platform ADMIN. |
| Sessions / login | JWTs contain a database-checked session version. Secretary credential changes and account/role changes invalidate old sessions. Production login throttling uses atomic shared PostgreSQL counters, by IP and account. |
| Headers | Same-origin frontend CSP, frame denial, MIME protection, referrer/permissions restrictions, HTTPS HSTS, API no-store, hidden Nginx version. |
| Static / dependency checks | Ruff security rules; npm advisory fix; weekly CI security checks and Dependabot configuration. Python dependency advisory fallback checks installed versions against PyPI. |
| Monitoring | Structured HTTP security events with generated request IDs and severity; omit bodies, passwords, tokens and query strings. Production launch commands disable Uvicorn's raw access log; Nginx access logs omit query strings. |

## Verification

- Full backend suite: **174 passed**. Explicit password-reset old-token regression
  and four additional hardening tests also passed in a targeted run.
- Strict mypy using `backend/pyproject.toml`: no issues in 60 application source files.
- Normal Ruff checks for application/new security scripts/tests and Ruff S-rules: pass.
- Fresh isolated PostgreSQL migration through `20261015_0030`: pass;
  Alembic schema drift check: no new operations. Existing cyclic users/institutes
  metadata warning remains and is not presented as fixed.
- Concurrent production limiter test: 20 attempts, exactly 5 allowed / 15 blocked.
- Local database backup saved privately to `backups/azari-before-security-20261015.dump`.
  Local database upgraded to 0030; bootstrap and backend restart completed.
- Frontend production Docker build and `nginx -t`: pass; updated frontend running
  at `http://localhost:4550`. Previous frontend container retained stopped for recovery.
- Local readiness/liveness: HTTP 200. Active manager and secretary student access:
  HTTP 200 using internally minted, unprinted tokens. This does **not** verify the
  user's remembered passwords; none were reset.
- npm audit: zero reported vulnerabilities after the source-map-js update.
- Running backend's 47 installed distributions: zero PyPI-feed advisory findings.
  Vulnerable unused pip installer was removed from that container; both production
  Dockerfiles now remove pip after installing dependencies.

## Verification limitations

- Fresh backend image build failed fetching build dependencies due to package-network
  connectivity. The local backend uses its existing dependency image, read-only
  mounted updated source and migrated database. The running container was patched
  to remove pip; recreating it from the **old image** restores the old pip installer.
  Build and audit the updated backend image on a network with working package access
  before deployment. Do not call this a successful clean backend image build.
- Installing pip-audit/Bandit was blocked by the same package-download connectivity.
  Ruff security rules and the PyPI advisory feed were used locally; this is not a
  claim that Bandit or pip-audit ran successfully. CI is configured to run pip-audit.
- Existing frontend suite has five previously reproduced unrelated baseline failures;
  the production build passes, but the whole frontend test suite is not green.
- These are targeted checks, not an exhaustive penetration test, OS-image vulnerability
  scan, availability guarantee, or certification that the app is secure.

## Before production deployment

1. Set `APP_ENV=production` explicitly, provide a unique private JWT secret and exact
   public origins, verify TLS, and review trusted reverse-proxy configuration. IP
   throttling must see the real client address without trusting spoofed headers.
2. Use a least-privileged application PostgreSQL role. The local Docker role is a
   superuser and bypasses RLS; production role provisioning/rotation was not performed.
3. If using Supabase's exposed API schema, review grants/RLS before exposing tables.
   Optional `python -m backend.scripts.security_database --harden-supabase` revokes
   browser-role table grants and enables default-deny RLS on existing app tables,
   using a reviewed server owner connection. It was **not** executed locally.
   It does not establish policies for Supabase Auth, future-table default privileges,
   or tenant restrictions for a privileged backend role.
4. Do not mix known demo accounts with real student data. Automatic demo import is
   blocked in production unless explicitly opted in; existing demo users are not
   silently deleted or disabled.
5. Publish the CI workflows after review, then configure security alert ownership,
   centralized log retention/alerts, backup retention/off-site storage and restore drills.
6. Session tokens remain accessible to JavaScript in browser session storage. Moving
   authentication to HttpOnly cookies requires a separate CSRF/session design;
   CSP reduces risk but does not eliminate XSS. No such migration is claimed here.
7. Secretaries cannot access institute aggregate financial reports. Operational student
   payment details remain available for their duties; totals could potentially be
   inferred from authorized records, so absolute financial secrecy is not claimed.

Existing browser tokens without the new session-version claim are intentionally
rejected: users must sign in again once after this update. Passwords are unchanged.

## References

- [Original checklist](https://www.fencer.dev/blog/how-to-secure-your-vibe-coded-app)
- [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
