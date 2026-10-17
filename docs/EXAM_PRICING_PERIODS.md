# Exam pricing periods

The exam catalog is grouped by institute, pricing period, grade and academic track.
Managers create date periods and select a period when creating an exam plan.
The courses page defaults to today's period and offers period/grade filters.
Secretaries can explicitly select an earlier period during registration.
Dates guide selection; choosing a historical period is intentionally allowed.
If periods overlap, the latest starting period is the default. All periods remain selectable.

Editing a price creates the next revision with a new ID. Earlier revisions remain
in the database, while new registrations can select only a current active revision.
Managers can show history and restore an earlier revision as another new version,
or copy its prices into a new period. Student invoice snapshots are not recalculated.
The original undated catalog remains under «تعرفه‌های قبلی بدون تاریخ».

Managers can remove classes, special-support items and exam plans from the catalog
using «حذف» and its confirmation dialog. Migration `20261015_0029` adds an
`is_deleted` flag, so no student invoice, payment or enrollment is deleted.
Deleted items are hidden from ordinary lists and refused by new registrations
and replacement-class/support operations. Removing an exam plan hides every
revision of that exact plan, grade, major and pricing period. Other periods remain.
Managers can select «نمایش موارد حذف‌شده برای بازیابی» and use «بازیابی» to
restore the item. Restoring an inactive item keeps its inactive status.
Secretaries cannot delete, restore or request the deleted catalog list.

## Spreadsheet source and interpretation

`backend/app/services/exam_pricing_catalog.json` contains 407 prices extracted from
`examsheet.xlsx`, `Sheet2!J1:AS40`: 37 grade/major combinations and 11 date groups.
The year 1405 comes from the dated column headings in row 3. The date groups come
from row 1, which takes precedence over the repeated `14050529` headings in row 3.

- «تا 15 اردیبهشت», «تا 31 اردیبهشت», «تا 31 خرداد», «تا 15 تیر» are inclusive end dates.
  The first has no supplied start date. Each following period starts after the prior end.
- «شروع از29 مرداد», «شروع 1 شهریور», «شروع 14 شهریور», «شروع 28 شهریور»,
  «شروع 5 مهر», «شروع 11 مهر», «شروع 18 مهر» are inclusive start dates.
  Each ends the day before the next start; the final group has no supplied end.
- The gap from 16 Tir through 28 Mordad is preserved; no prices are invented for it.
- Values are rials and all 407 exam totals reconcile with count × unit price.
  Book voucher amounts and discounts are copied from the shared row values.
- Grade 1 has no supplied exam pricing.

## Existing databases

Managers can also open `/courses` and click «بارگذاری بازه‌ها و قیمت‌های فایل آزمون».
This authenticated, rate-limited POST imports missing workbook entries into the
**currently selected institute only**, records an audit event, and preserves
legacy prices, edited revisions, custom periods and student invoices. Repeating
it does not duplicate prices. Secretaries cannot perform the import.

The «بازه قیمت آزمون» selector lists dated periods chronologically, including past
dates; choosing one displays its prices grouped by grade. «همه بازه‌ها» displays
all periods and the separate undated legacy catalog. Managers can use
«نمایش نسخه‌های قبلی قیمت‌ها» to inspect older revisions within a period. GET requests
remain read-only; missing dates are never silently imported when the page opens.

Back up the database, apply Alembic revision `20261015_0028`, then run:

```sh
python -m backend.scripts.import_exam_pricing --manager-email demo.school.manager2@example.com
```

This appends missing workbook periods and prices to every institute belonging to
the named manager. It is safe to repeat and does not overwrite old prices,
students, payments or passwords. Choose the intended manager email explicitly.
New empty school catalogs and fresh demo imports include the dated workbook data.
An existing deployment should run the command after migrations; the import does
not silently replace an existing school's custom catalog during normal requests.
