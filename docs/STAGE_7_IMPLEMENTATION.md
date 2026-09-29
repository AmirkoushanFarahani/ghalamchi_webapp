# Stage 7 — Production Frontend

Implementation date: 2026-08-25

## Scope and boundary

Stage 7 replaces the Vite connectivity shell with the production frontend. It
does not change an API route, Pydantic schema, database model, migration,
accounting rule, reporting query, ML pipeline, registry rule, or permission.
The existing backend remains the source of truth. Stage 8 was not started.

## Frontend architecture

The React client is divided into `auth`, `theme`, `routes`, `layouts`, `pages`,
`components`, `services`, `types`, `hooks`, and `utils`. One typed API service
adds bearer tokens, translates expected HTTP errors into Persian, handles 401
logout, and preserves backend 403 enforcement. JWTs are stored only for the
browser session. Protected route checks and permission-aware navigation improve
usability but are not treated as a security boundary.

Reusable page headers, cards, loading/empty/error states, dialogs, confirmation
flows, fields, status badges, financial display, and dependency-light SVG/CSS
charts keep API pages consistent. Forms submit only fields accepted by the
Pydantic contracts. Invoice previews are labeled as previews; invoice totals,
journal balance/posting, payment allocation, and status remain authoritative on
the backend.

## Persian, RTL, and accessibility

The HTML root is `lang="fa" dir="rtl"`; all operational labels, actions,
validation, empty/error states, navigation, and guidance are Persian. Numeric
utilities use `en-US` with the `latn` numbering system for English digits,
thousands separators, two-decimal money, percentages, and visible negatives.

IRANSans/IRANSansX are preferred only when already licensed and installed. The
shipped fallback stack is Vazirmatn, Tahoma, Arial, and sans-serif; no commercial
font file or remote font request was added. Controls have at least 44px targets,
strong focus styles, sufficient theme contrast, explicit labels, keyboard-close
dialogs, status text in addition to color, reduced-motion support, and print CSS.

## Theme, navigation, and responsive behavior

Light is the default. A designed dark token set covers surfaces, borders, text,
dialogs, tables, charts, warnings, and financial states. The choice persists in
local storage. Desktop uses a grouped top navigation bar. At 1220px and below it
becomes a scrollable right-side drawer with a backdrop and touch-size links.

Dashboards change from multi-column to stacked layouts. Master-data cards reduce
from three to two to one column. At mobile widths normal accounting tables become
labeled record cards, complex forms regroup, and dialogs become bottom sheets.
Dense forecast tables retain deliberate horizontal scrolling because collapsing
their numeric columns would make comparisons ambiguous.

## Calendar handling

Users can persist either Jalali or Gregorian presentation/input. Shared date
fields label the active calendar and convert Jalali input to ISO Gregorian before
API submission. Database and backend date architecture are unchanged. Conversion
uses the Borkowski implementation adapted from MIT-licensed `jalaali-js` 2.0.1;
the exact commit and notice are in `frontend/THIRD_PARTY_NOTICES.md`.

## Implemented workflows

- Login, current user, logout, protected routes, 401 expiry, and Persian 403 UI.
- Dashboard KPIs, cash-flow chart, recent invoices/payments, overdue follow-up,
  and recent AI activity, all from persisted API responses.
- Parties and products list/create/edit; chart of accounts and category creation;
  financial period creation/status/confirmed close.
- Journal list/detail/draft creation with visible debit/credit balance, confirmed
  post, and reversal.
- Invoice list/create/detail/backend-total display and confirmed issue with
  receivable/revenue accounts.
- Payment list/create/detail, invoice allocations, allocation-total validation,
  and confirmed posting with cash/receivable accounts.
- Trial balance, income statement, balance sheet, revenue, expenses,
  receivables, payables, cash flow, and party history with only their supported
  date/as-of/customer filters and printable output.
- User list for `users:read`. The API exposes no user or role mutation, so none
  is invented in the frontend.

## AI integration

- AI dashboard lists active/available models, prediction totals, review counts,
  history, confidence, and feedback state.
- Transaction classification shows category, confidence, manual-review advice,
  version/time, and append-only feedback.
- Payment-delay risk selects a real invoice and as-of date and displays risk,
  probability, returned signals, and explicit uncertainty language.
- Cash-flow forecasting displays the requested horizon, forecast curve,
  predicted/lower/upper values, and clearly labels it as prediction rather than
  historical accounting data.
- Customer segmentation selects a real customer and shows the backend's
  behavioral description rather than using the raw cluster number as meaning.
- `ml:manage` users can register a controlled artifact identifier, view versions
  and synthetic-data status, and confirm activation. No filesystem path, model
  binary, credential, or training workflow is exposed.

## API integration

The frontend uses these existing contracts:

- `POST /auth/login`, `GET /auth/me`, `GET /users`
- `/parties`, `/products`, `/account-categories`, `/accounts`, `/periods`
- `/journals` plus `/{id}/post` and `/{id}/reverse`
- `/invoices` plus `/{id}/issue`
- `/payments` plus `/{id}/post`
- `/dashboard`
- `/reports/trial-balance`, `/income-statement`, `/revenue`, `/expenses`,
  `/balance-sheet`, `/receivables`, `/payables`, `/cash-flow`, and
  `/reports/parties/{party_id}/history`
- `/ml/models`, `/ml/models/register`, `/ml/models/{id}/activate`,
  `/ml/predictions`, `/ml/predictions/{id}/feedback`,
  `/ml/transactions/classify`, `/ml/payment-risk/predict`,
  `/ml/cash-flow/forecast`, and `/ml/segmentation/predict`

No backend API change was necessary, so `docs/API.md` is unchanged.

## Tests and verification

- Frontend TypeScript: passed with `tsc --noEmit`.
- Frontend production build: passed; 47 modules transformed, JS 283.86 kB
  (81.21 kB gzip), CSS 23.88 kB (5.85 kB gzip).
- Frontend tests: 12 passed. Coverage includes JWT contract, protected/
  permission-aware navigation, Persian RTL root, API error translation,
  English-digit money/percent formatting, Jalali round trip, important form,
  dashboard KPI, report result, AI forecast workflow, and theme defaults.
- Backend/ML regression: 67 passed. The suite emitted existing dependency
  deprecations and a Windows warning that pytest could not write its cache; no
  test failed.
- Ruff: passed.
- Strict mypy: passed across 91 source files.
- `docker compose config`: passed with frontend `4173:80`, backend `8100:8000`,
  and PostgreSQL internal.
- Stage 7 frontend image: rebuilt successfully with 47 modules transformed.
- Final Compose runtime: PostgreSQL healthy, backend healthy, frontend running;
  backend health returned HTTP 200 at port 8100 and the Persian RTL frontend
  returned HTTP 200 at port 4173.
- `git diff --check`: passed.

An initial full parallel image rebuild and a later isolated backend rebuild were
blocked while the host could not reach PyPI to download the backend build
dependency `setuptools`. This was an external timeout, not a compile/test error.
The unchanged, previously verified Stage 6 backend image was used for the final
healthy runtime; the Stage 7 frontend image itself was rebuilt from source.

## Known limitations

- The accounting domain has no supplier-bill/outgoing-payment document. The
  frontend truthfully shows liability-account exposure and explains that
  supplier-level payable detail is unavailable.
- User and role mutation endpoints do not exist, so the management UI is
  read-only for users and does not pretend to edit roles.
- Backend report APIs do not provide grouped revenue/expense time-series or
  server pagination. The client therefore does not invent trend points or fake
  pagination.
- Active ML artifacts and metrics remain synthetic/demo quality as documented
  in Stages 5 and 6.
- Uncached backend image rebuilds currently require restored outbound access to
  PyPI on this host. The running Compose backend is healthy.

## Result

Stage 7 is **PASS**. The required frontend, regression, configuration, rebuilt
frontend image, and live three-service runtime gates pass. Stage 8 was not
started.
