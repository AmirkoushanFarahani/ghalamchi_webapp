# Stage 2 — Persistence and Identity

Implementation date: 2026-08-17

## Scope

Stage 2 implements only the persistence and identity foundation. No customers,
suppliers, products, accounting entities, reports, or ML functionality were
added.

## Persistence

The backend uses SQLAlchemy 2.x typed mappings and one synchronous session per
request. UUIDs identify users, roles, permissions, and audit events. Database
timestamps use timezone-aware columns and PostgreSQL server defaults. Alembic is
the deployment schema authority; `Base.metadata.create_all()` appears only in
isolated SQLite unit-test setup.

Migration `20260817_0001` creates `users`, `roles`, `permissions`, `user_roles`,
`role_permissions`, and `audit_events`, including named unique constraints,
composite relationship keys, foreign keys, indexes, and explicit referential
actions.

## Identity and RBAC

Canonical roles are ADMIN, ACCOUNTANT, MANAGER, and VIEWER. Permissions stored
in PostgreSQL are:

- `users:read`, `users:create`, `users:update`, `users:delete`;
- `accounting:read`, `accounting:write`;
- `reports:read`;
- `ml:read`, `ml:train`.

The bootstrap is deterministic and idempotent. Public registration always
assigns VIEWER and rejects extra input, preventing role injection. Optional
development administrator credentials come only from paired environment
variables and are validated; no administrator password is hardcoded.

`require_authenticated_user` centralizes token authentication and
`require_permission(name)` centralizes permission checks. Permissions are the
union inherited through all assigned roles. API behavior is 401 for absent,
invalid, expired, unknown-user, or inactive-user tokens and 403 for an
authenticated user lacking a required permission.

## Passwords and tokens

Passwords are bounded at API input and hashed with Argon2id. Only
`password_hash` is stored, and safe schemas never expose it. JWT access tokens
contain only subject UUID, token type, issued/expiry timestamps, and a token ID.
Secret, algorithm, and lifetime come from validated environment settings. Only
HMAC SHA-2 algorithms are accepted. Refresh tokens are intentionally omitted.

## Audit strategy

Registration and login success/failure create append-oriented audit events. An
event contains an optional actor, action, resource type/ID, time, success flag,
and limited metadata. The repository defensively rejects metadata keys that
could contain passwords, hashes, tokens, secrets, authorization headers, or
credentials. There is no API for changing or deleting audit history.

## Verification strategy

Fast unit/integration-style API tests use isolated in-memory SQLite only for
portable service behavior. PostgreSQL-specific schema, migration, timezone,
relationship, and uniqueness behavior is separately exercised against the
dedicated `azari_stage2_test` database. The verification refuses to run against
any other database name.

Executed gates:

- pytest on Python 3.12: 25 passed, 94% application coverage;
- Ruff: all checks passed;
- strict mypy: no issues in 38 source files;
- frontend TypeScript/Vite build: passed, 30 modules transformed;
- isolated PostgreSQL: upgrade, bootstrap, schema/constraint/timezone checks,
  downgrade, and final upgrade passed;
- Alembic drift check: no new upgrade operations detected;
- live API: registration, login, `/auth/me`, safe response fields, 401, 403,
  failed-login auditing, health, and OpenAPI route presence verified;
- final Compose rebuild: PostgreSQL healthy, backend healthy on host port 8100
  mapped to container port 8000, frontend reachable on host port 4173 mapped to
  container port 80, and all three services running;
- host endpoint checks: `/api/v1/health` returned HTTP 200 through port 8100 and
  the frontend returned HTTP 200 through port 4173.

The dedicated `azari_stage2_test` database was removed after verification. It
contained only disposable migration-test data.

## Security decisions and limitations

- Login failures use one generic response to reduce account enumeration.
- Public registration still reveals duplicate-email conflicts as required by
  the specification.
- Access tokens are short-lived but have no server-side revocation or refresh
  mechanism in Stage 2.
- Rate limiting, email verification, password reset, MFA, and user/role mutation
  administration remain future security work.
- The single-organization assumption remains; tenant isolation is not present.
- Audit events are application-append-only, but database administrators retain
  normal database-level control.

## Result

Stage 2 is **PASS**. The host-port adjustment was reverified on 2026-08-18 with
the full Compose stack, backend tests, Ruff, strict mypy, and the frontend
production build. Stage 3 has not started.
