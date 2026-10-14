# Student class changes

Both manager and secretary can open a student record and select **تغییر کلاس / دبیر**.
The replacement must be active, in the same institute and grade, and not already
selected in that enrollment. It may be a different subject in the same grade.
This changes only the student's enrollment, not the manager's class catalog.

The server uses the originally charged class price and the replacement's current
catalog price. Previously negotiated discount **amounts** are preserved (capped
at the new subtotal), rather than reapplying a possibly edited discount code.
Book, exam and support fees are unchanged. A more expensive class increases the
tuition balance; staff can record its difference immediately or collect later.
Checks/installments require a due date and count as received only after clearing.

For a cheaper class, unpaid tuition is reduced. Any already-paid excess remains
student credit in this enrollment, usable against subsequent class upgrades here.
Credit is not automatically transferred to other students or registrations.
Staff records the student's preference: retain credit or request a refund.
Only the manager can confirm a refund after money has actually been returned
(cash/bank transfer, date and optional tracking code). No bank transfer is executed
by the software. The original receipt is preserved; net received tuition and cash
summaries subtract confirmed refunds. Pending refunds do not decrease cash.
Further class switches wait until a pending refund is confirmed or cancelled
with the student's agreement, preventing accidental consumption of requested credit.

Existing checks/installments are never silently repriced or deleted. Review the
schedule after a cheaper replacement. Cancel superseded unpaid entries and add
a replacement payment from the student record if necessary. Cleared payments
and cancelled entries cannot be changed; over-collection is rejected.

Changes, reasons, original/replacement teacher and price snapshots, refund
decisions and payment actions are retained in the student history/audit trail.
Older enrollments have no historical teacher snapshot; these are explicitly
labelled as unavailable rather than inventing a past teacher from today's catalog.
New enrollments and replacements save instructor snapshots.

Migration `20261014_0025` adds the history table, nullable instructor snapshot,
and cancelled payment status. It does not rewrite existing tuition/payments.
All payment, refund and class-change writers lock the enrollment before modifying
balances. Client price snapshots prevent a stale price preview being accepted.
Apply Alembic migrations before serving the new frontend. Existing demo snapshots
remain importable without change-history records.

## Verification (2026-10-14)

- Full backend suite: 160 tests passed, including 9 new class-change cases.
- TypeScript/production build, targeted Ruff and strict mypy: passed.
- Frontend suite: 34/37 passed, including both new class-change tests. The same
  three unrelated failures also occur on the previous commit (business-profile
  navigation, existing amount-format expectation, supplier-bill source assertion).
- Isolated PostgreSQL: complete migration chain, schema drift check, downgrade
  and re-upgrade of revision 0025 passed.
- Real API on isolated PostgreSQL: extra payment, cheaper replacement, refund
  permission denial, manager-confirmed refund and receipt preservation passed.
- Concurrent PostgreSQL switches: one success, one rejected; exactly one history
  entry and one tuition adjustment were recorded.
- Local Docker refreshed on port 4550; existing database backed up and preserved.

Frontend checks are module/source/SSR checks, not a browser end-to-end test.
