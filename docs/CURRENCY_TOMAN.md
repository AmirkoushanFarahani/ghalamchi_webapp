# Currency contract: تومان (TOMAN)

All business money in the database, public API requests/responses, form inputs,
reports, balances, refunds and dashboard cards is now **Toman**. The API sends
`X-Monetary-Unit: TOMAN`. Enter **1,000,000** for one million Toman; neither the
browser nor the normal API handlers divide this amount again.

## One-time conversion

Migration `20261021_0032`, after `20261020_0031`, divides the 62 existing monetary
columns by **10**. This includes catalogs, invoices/purchases, tax amounts,
journals, allocations, tuition, payment plans/checks, expenses, saved class/support
changes, cancellations and refund snapshots. Counts, quantities, percentage
discounts, grades, school years, identities and dates do not change.

The migration refuses precision loss instead of silently rounding. For example,
0.01 Rial would require 0.001 Toman, outside the current two-decimal schema. Such a
database must be reviewed explicitly. The local demo's values passed this check.
All updates and Alembic's revision marker are transactional: a failed upgrade
rolls back; re-running `upgrade head` does not divide amounts again.

Existing structured audit amounts and forecast history points are converted.
Original free-form comments, feedback and historical documents are not rewritten;
legacy forecast feedback retains an explicit `legacy_feedback_currency: IRR` tag.
New monetary audit events and forecast values are tagged TOMAN.

## Source data and ML compatibility

- Original workbook-derived JSON and the old bundled demo snapshot remain Rial
  source material. Their importers convert at that explicit boundary, not on reads.
- New demo exports include `currency: TOMAN`; re-import does not convert them again.
  Old snapshots without a unit are treated as IRR. Percentages are never converted.
- New seed scripts use Toman. Do not re-run old seed code against the new schema.
- Existing trusted ML artifacts are left byte-for-byte unchanged, including their
  digests. Monetary features are scaled back to the model's training unit at
  inference; forecast results are returned/stored in Toman. New artifacts can
  explicitly set `training_configuration.currency` to TOMAN; untagged legacy
  artifacts default to IRR. Counts, ratios and probabilities are not scaled.

## Deployment/rollback

1. Take a private PostgreSQL backup (never commit it or `.env`).
2. Stop every app writer/worker and disconnect old browser sessions.
3. Run `alembic upgrade head` using the new code against the intended database.
4. Start the matching backend/frontend release together; refresh open tabs.
5. Check 10,000,000 Rial becomes 1,000,000 Toman, balances still reconcile,
   and new entries preserve the amount entered.

Do not run the old release on a converted database. An automatic downgrade is
blocked: restore the backup and old release together if rollback is necessary.
Production migration/deployment is a separate authorized operation; changing the
local Docker database does not update inkcollection.ir.

Verification uses synthetic tests, an isolated restored PostgreSQL database and
`backend/scripts/verify_toman_migration.py`. No real records are used for attacks.
Security: tenant/RBAC behavior is unchanged; no public upload/fetch/payment
integration added (N/A). Live production checks remain pending authorization.

Verification results: 197 backend tests passed; frontend build, targeted Toman
format/input tests and the real-browser registration test passed. The full
frontend suite has 40 passing tests and the same five unrelated baseline failures.
The dependency audit also reports an existing high-severity Vite advisory;
dependency upgrades were not included in this currency-only change.
