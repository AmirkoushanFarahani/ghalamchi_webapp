# Academic years and repeat registration

- In **کلاس‌ها و شهریه‌ها**, choose a school year. Classes, exam plans and price
  periods are displayed only for that year. Managers can create years and edit
  their teaching dates; secretaries can only select/read them.
- Initial years are **1405/1406** and **1406/1407**, from Mehr 1 to Khordad 31.
  Dates are editable per institute. Teaching dates do not limit advance
  registration or the separate exam pricing windows (which may start earlier).
- New class/exam forms send the year explicitly. A class or exam revision cannot
  be moved to another year: create a new class/plan instead. Copying an exam plan
  permits choosing another year and that year's pricing period.
- The bundled workbook belongs to **1405/1406 only**; importing it never copies
  its prices into future years. Define future-year prices explicitly.
- Registration selects a year and grade. Only matching active classes and exam
  plans are accepted, with the same checks enforced by the backend.
- Enter the national code and use **بازیابی اطلاعات** to reuse a student's identity.
  The server also reuses the identity if a caller skips lookup. Re-registration
  never overwrites the existing student's personal details. Staff choose the new
  year, grade and services. Multiple enrollments in the same grade/year are allowed.
- Identity reuse is within the selected institute, not across schools. Each
  enrollment snapshots its grade, major, registration date, school year and prices.
  Student-level grade/date remain the original registration; enrollment detail and
  tuition reporting use the enrollment snapshots. Class changes must stay in the
  enrollment's grade AND year, including changes to an older registration.

## Migration and verification

Revision `20261020_0031` follows `20261015_0030`. Existing classes, exam prices,
pricing windows and enrollments are assigned to the user-confirmed **1405/1406**.
Enrollment grade/major/date are backfilled from the existing student. No monetary
amounts, payments, exam revisions or identities are rewritten. Older API clients
that omit the year default to 1405/1406 for backward compatibility; current forms
send an explicit selection. Review this backfill assumption before applying the
migration to an installation with records from other school years.

Take a private database backup before upgrading. Do not commit backups or `.env`.
Automatic downgrade is blocked because merging years could lose history.

Verification includes synthetic two-school/two-secretary/unrelated-manager tests,
repeat registrations and historical payment preservation, year/grade mismatch
rejection, calendar conversions, and a real headless Chrome registration test
with synthetic HTTP fixtures (`frontend/tests/academic-years.browser.mjs`).
Fresh and populated isolated PostgreSQL migrations and Alembic metadata checks
are run before upgrading the local Docker database. GET requests never seed years.

Security: PASS for authenticated/scoped year reads/writes and student lookup;
N/A for new uploads, webhooks, URL fetching or cookie authentication (none added).
Production deployment and live security checks remain pending user authorization.
