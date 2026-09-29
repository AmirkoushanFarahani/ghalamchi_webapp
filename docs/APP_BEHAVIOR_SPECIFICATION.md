# Azari Accounting — Application Behavior Specification

This document describes how the application **must behave from a user's point
of view**. It is a review document, not a claim that every behavior is already
implemented correctly. The English specification appears first; the complete
Persian version follows it.

---

## English

### 1. Product principles

- The application is a real accounting system, not a dashboard demo.
- Every number must come from persisted user-entered accounting data.
- Opening, refreshing, or revisiting a page must never create records or change
  financial totals.
- Example, test, seed, and ML-training data must never appear in a real user's
  company dashboard unless the user explicitly imports it into a clearly marked
  demo environment.
- Financial calculations and status changes are controlled by the backend. The
  frontend may show previews, but it must not invent authoritative totals.
- A successful action must show a clear success result. A failed or blocked
  action must show a clear Persian explanation and the next action the user can
  take. Silent failure is not acceptable.

### 2. Language, direction, and visual presentation

- The business interface is Persian and right-to-left.
- The shipped application must load a licensed, self-hosted IRANSans webfont;
  merely naming IRANSans in CSS is not sufficient. All controls, tables, modals,
  and responsive views must inherit it consistently.
- Numbers used for money, invoice numbers, codes, and technical identifiers use
  readable English digits and left-to-right presentation where appropriate.
- Dates can be displayed as Jalali or Gregorian according to the user's setting,
  while API storage and transport remain Gregorian ISO dates.
- Desktop, tablet, and mobile layouts must preserve labels, actions, and table
  context without horizontal loss or inaccessible controls.

### 3. Registration, login, and sessions

- The login page provides visible actions for both **Login** and **Register**.
- Registration asks for first name, last name, email and phone number, password,
  and password confirmation. At least one of email or phone number is required;
  either or both may be supplied. Passwords must contain 12–128 characters.
- Login accepts either the account's email address or E.164 phone number with
  the password.
- Registration assigns the server-selected `OWNER` role. It grants every
  non-user-management permission so the registrant retains full operational
  control of their private workspace, but it excludes every `users:*`
  permission and cannot be overridden by request input.
- After successful registration, the user is logged in and taken to the first
  page their role is allowed to access.
- Duplicate email or phone number, invalid input, incorrect credentials, expired
  sessions, and network failures must be explained in Persian.
- Logout removes the local session and returns the user to login.

### 4. Users, roles, and permissions

- Every visible page and action follows backend permissions.
- The UI hides or disables actions the user cannot perform, but the backend is
  always the final security boundary.
- A newly registered user receives `OWNER`, so all accounting, reporting and ML
  actions are visible immediately while platform user management remains hidden.
- A forbidden action returns a Persian access message, not a broken or empty
  screen.

### 5. Initial setup and prerequisites

Before normal accounting work, an authorized user must be able to configure:

1. Account categories and active ledger accounts.
2. At least one open financial period.
3. Active customer and/or supplier parties.
4. Optional products and services.

When a required selection has no options, the form must explain the missing
prerequisite in Persian, link to the relevant setup page, and prevent submission.
The browser must not silently block the form.

### 6. Parties and products

- A party can be a customer, supplier, or both, and can be active or inactive.
- Only active customers appear in customer selectors.
- Inactive records remain visible historically but cannot be used for new
  transactions.
- Products/services provide reusable descriptions and prices. An invoice line
  may also be entered without selecting a product when the API allows it.
- Editing master data must not rewrite historical invoice or journal values.

### 7. Invoice (factor) workflow

#### Create a draft

- An authorized user opens **Invoices** and selects **New invoice**.
- The form requires a unique invoice number, an active customer, issue date, due
  date, and at least one valid line.
- Each line contains a description, positive quantity, non-negative unit price,
  and non-negative tax. A product link is optional.
- The frontend shows a clearly labeled preview. The backend recalculates and
  stores the authoritative subtotal, tax, and total.
- An invoice whose authoritative total is zero is rejected.
- Clicking save once creates exactly one draft invoice. The submit button is
  disabled while the request is running to prevent accidental duplicates.
- On success, the modal closes, the invoice list refreshes, and a Persian success
  message identifies the created invoice.
- On failure, entered data remains available and a specific Persian error is
  displayed. The form must never appear to do nothing.

#### Draft behavior

- A draft invoice is operational data but is **not posted accounting revenue**.
- Creating or viewing a draft must not change revenue, receivables, trial balance,
  income statement, or cash flow.
- Drafts may be reviewed and, where supported, edited before issue.

#### Issue an invoice

- Issuing requires the proper permission, an open period, and active accounts
  explicitly assigned the `RECEIVABLE` and `REVENUE` posting roles. A taxed
  invoice also requires an active `TAX_LIABILITY` account; broad account
  category alone is not sufficient.
- The user sees a confirmation explaining that issue creates accounting entries.
- One successful issue creates one balanced posted journal, debits receivables
  for the total, credits revenue for the subtotal, credits tax liability for
  tax (when nonzero), changes the invoice to `ISSUED`, and updates reports once.
- Repeated clicks, refreshes, retries, or issuing an already issued invoice must
  not duplicate the journal or increase dashboard values again.
- A source-generated journal cannot be independently reversed while leaving the
  invoice unchanged. Correction requires a dedicated invoice cancellation or
  credit-note workflow.

### 8. Payment/receipt workflow

- A receipt requires an active customer and at least one issued or partially paid
  invoice with an outstanding balance for that customer.
- Allocations must be positive, must belong to the selected customer, must not
  exceed invoice balances, and their sum must equal the receipt amount.
- Saving creates one draft receipt and does not affect posted cash totals.
- Posting creates one balanced journal and applies allocations atomically. Either
  all changes succeed or none do.
- A full allocation changes the invoice to `PAID`; a smaller allocation changes
  it to `PARTIALLY_PAID`.
- Posting or retrying the same receipt must never count it more than once.

### 9. Manual journals and financial periods

- A manual journal requires a unique number, date in an open period, description,
  at least two valid lines, and active accounts.
- Every line is one-sided and non-negative; total debits must equal total credits
  and must be greater than zero.
- Draft journals do not affect reports. Posting is atomic and affects reports once.
- Posted journals are immutable. A valid manual reversal creates one opposite
  posted journal and cannot itself be repeated.
- Closing a period prevents new or changed postings in that period.

### 10. Dashboard behavior

- The dashboard is a read-only summary. Loading it must never write to the
  database.
- Values are calculated from persisted, posted records at a clear reporting date.
- Draft invoices, draft receipts, draft journals, page visits, browser refreshes,
  health checks, and AI predictions do not change dashboard financial values.
- Issuing one invoice changes the appropriate revenue and receivable totals once.
- Posting one receipt changes cash flow, paid amount, and outstanding receivables
  once. It does not create additional revenue.
- Re-fetching the dashboard returns the same values when no accounting record has
  changed.
- Empty businesses show zero/empty states rather than fabricated sample values.
- Every dashboard card must have a documented definition and must reconcile with
  the corresponding report.

### 11. Reports

- Trial balance, income statement, balance sheet, revenue, expenses, receivables,
  payables, cash flow, and party history are read-only.
- Reports use posted records only, with documented exceptions for operational
  invoice status views.
- Date and party filters must be visible, deterministic, and validated.
- Report totals must reconcile with the ledger and relevant dashboard cards.
- Printing must retain titles, filters, dates, column labels, and totals.

### 12. AI features

- AI classification, payment risk, cash-flow forecast, and customer segmentation
  are decision-support tools, not accounting postings.
- Running a prediction may append an auditable prediction record, but it must not
  change invoices, journals, payments, balances, revenue, or dashboard totals.
- Results identify the active model version, show uncertainty or confidence, and
  use Persian explanations and safe fallbacks.
- Synthetic models and data are clearly labelled and are never presented as
  proven real-world accuracy.

### 13. Errors, feedback, and reliability

- Forms show loading state and prevent duplicate submission.
- Success, validation, conflict, permission, authentication, server, and network
  outcomes have distinct Persian messages.
- A failed multi-record accounting operation rolls back completely.
- Refreshing after any operation shows the persisted server state.
- No password, token, raw credential, or secret is written to logs, UI errors, or
  Git.

### 14. Acceptance scenarios for the reported problems

#### Invoice creation

1. Create an active customer, an open period, and active accounts with
   `RECEIVABLE`, `REVENUE`, and `TAX_LIABILITY` posting roles.
2. Sign in with an account that has invoice write/issue permissions.
3. Create invoice `TEST-001` with one line for 100 and tax 10.
4. Exactly one draft with total 110 must appear.
5. The posted dashboard and reports must remain unchanged while it is a draft.
6. Issue it once; receivables increase by 110, revenue by 100, and tax
   liability by 10.
7. Refresh the browser repeatedly; the totals must remain unchanged.
8. A second issue attempt must be rejected without any new journal or total.

#### Dashboard stability

1. Record all dashboard values and database record counts.
2. Refresh the dashboard ten times and navigate away/back.
3. Values and record counts must remain identical.
4. Run each AI prediction once; financial dashboard values must remain identical.
5. Only a successful accounting posting may change the relevant financial cards.

### 15. Currently reported issues awaiting implementation decisions

- The user reports that a new invoice cannot be added. This must be reproduced to
  determine whether the cause is permissions, missing prerequisites, frontend
  submission behavior, or an API/domain error.
- The user reports dashboard numbers increasing repeatedly. This must be traced
  from the displayed card through the report API to persisted records; no data
  should be deleted or reset merely to hide the cause.
- The application names IRANSans in CSS but does not contain a licensed IRANSans
  webfont asset. A licensed WOFF2 file must be supplied and self-hosted before the
  font requirement can be considered complete.

---

## فارسی

### ۱. اصول محصول

- برنامه باید یک سامانه حسابداری واقعی باشد، نه یک داشبورد نمایشی.
- تمام اعداد باید از اطلاعات حسابداری ثبت‌شده و ماندگار کاربر به دست بیایند.
- بازکردن، تازه‌سازی یا مراجعه دوباره به یک صفحه نباید رکوردی ایجاد کند یا مبلغی
  را تغییر دهد.
- اطلاعات نمونه، آزمایشی، Seed و داده‌های آموزش مدل نباید در داشبورد واقعی شرکت
  نمایش داده شوند؛ مگر اینکه کاربر آن‌ها را آگاهانه در یک محیط نمایشی مشخص وارد
  کرده باشد.
- محاسبات مالی و تغییر وضعیت‌ها در سرور انجام می‌شوند. رابط کاربری می‌تواند
  پیش‌نمایش نشان دهد، اما نباید عدد قطعی ساختگی تولید کند.
- هر عملیات موفق باید نتیجه روشن داشته باشد. هر عملیات ناموفق یا مسدودشده باید
  دلیل و اقدام بعدی را به فارسی توضیح دهد. شکست بی‌صدا قابل قبول نیست.

### ۲. زبان، راست‌به‌چپ و ظاهر

- رابط کاری برنامه فارسی و راست‌به‌چپ است.
- نسخه نهایی باید فایل دارای مجوز فونت IRANSans را به‌صورت محلی بارگذاری کند؛
  نوشتن نام IRANSans در CSS به‌تنهایی کافی نیست. تمام کنترل‌ها، جدول‌ها، مودال‌ها
  و نماهای واکنش‌گرا باید همین فونت را به ارث ببرند.
- مبالغ، شماره فاکتور، کد حساب و شناسه‌های فنی در محل مناسب با ارقام انگلیسی و
  جهت چپ‌به‌راست نمایش داده می‌شوند.
- تاریخ بر اساس تنظیم کاربر شمسی یا میلادی نمایش داده می‌شود، اما ذخیره و انتقال
  API همچنان با تاریخ میلادی ISO انجام می‌شود.
- نسخه دسکتاپ، تبلت و موبایل نباید برچسب‌ها، عملیات یا مفهوم ستون‌های جدول را از
  دست بدهد.

### ۳. ثبت‌نام، ورود و نشست کاربری

- صفحه ورود باید هر دو گزینه روشن «ورود» و «ثبت‌نام» را داشته باشد.
- ثبت‌نام شامل نام، نام خانوادگی، ایمیل، شماره تلفن، رمز عبور و تکرار رمز عبور
  است. واردکردن حداقل یکی از ایمیل یا شماره تلفن الزامی است و کاربر می‌تواند هر
  دو را نیز وارد کند. طول رمز عبور باید بین ۱۲ تا ۱۲۸ نویسه باشد.
- ورود با ایمیل یا شماره تلفن استاندارد E.164 به‌همراه رمز عبور انجام می‌شود.
- ثبت‌نام نقش `OWNER` را در سرور به کاربر می‌دهد. این نقش همه مجوزهای عملیاتی
  به‌جز مجوزهای `users:*` را دارد تا کاربر فضای کاری خصوصی خودش را کامل مدیریت
  کند، اما نتواند کاربران دیگر سامانه را مشاهده یا مدیریت کند.
- پس از ثبت‌نام موفق، کاربر وارد برنامه می‌شود و به اولین صفحه مجاز هدایت می‌شود.
- ایمیل یا شماره تلفن تکراری، اطلاعات نامعتبر، رمز اشتباه، پایان نشست و خطای شبکه
  باید با پیام فارسی روشن نمایش داده شوند.
- خروج باید نشست محلی را پاک کند و کاربر را به صفحه ورود برگرداند.

### ۴. کاربران، نقش‌ها و مجوزها

- نمایش هر صفحه و عملیات باید مطابق مجوزهای سرور باشد.
- رابط کاربری عملیات غیرمجاز را مخفی یا غیرفعال می‌کند، اما کنترل نهایی امنیت
  همیشه در سرور باقی می‌ماند.
- کاربر تازه ثبت‌شده نقش `OWNER` دارد؛ همه عملیات حسابداری، گزارش و هوش مصنوعی
  برای او نمایش داده می‌شوند، اما مدیریت کاربران سامانه نمایش داده نمی‌شود.
- عملیات غیرمجاز باید پیام فارسی نشان دهد، نه صفحه خالی یا خراب.

### ۵. راه‌اندازی اولیه و پیش‌نیازها

پیش از کار حسابداری عادی، کاربر مجاز باید بتواند موارد زیر را تنظیم کند:

۱. سرفصل‌ها و حساب‌های فعال دفتر کل.
۲. حداقل یک دوره مالی باز.
۳. طرف حساب فعال از نوع مشتری یا تأمین‌کننده.
۴. کالا و خدمات در صورت نیاز.

اگر یک فهرست اجباری هیچ گزینه‌ای ندارد، فرم باید پیش‌نیاز مفقود را به فارسی
توضیح دهد، به صفحه تنظیم مربوط پیوند بدهد و ارسال را متوقف کند. مرورگر نباید فرم
را بدون توضیح مسدود کند.

### ۶. طرف حساب‌ها و کالاها

- طرف حساب می‌تواند مشتری، تأمین‌کننده یا هر دو باشد و وضعیت فعال/غیرفعال دارد.
- فقط مشتری فعال در انتخاب‌گرهای مشتری نمایش داده می‌شود.
- رکورد غیرفعال برای سابقه باقی می‌ماند، اما در تراکنش جدید قابل استفاده نیست.
- کالا/خدمت، شرح و قیمت قابل استفاده مجدد فراهم می‌کند. در صورت پشتیبانی API،
  قلم فاکتور می‌تواند بدون اتصال به کالا نیز ثبت شود.
- ویرایش اطلاعات پایه نباید مقادیر تاریخی فاکتور یا سند را بازنویسی کند.

### ۷. فرایند فاکتور

#### ساخت پیش‌نویس

- کاربر مجاز وارد بخش «فاکتورها» می‌شود و «فاکتور جدید» را انتخاب می‌کند.
- شماره یکتای فاکتور، مشتری فعال، تاریخ صدور، سررسید و حداقل یک قلم معتبر اجباری
  هستند.
- هر قلم شامل شرح، تعداد مثبت، قیمت واحد و مالیات نامنفی است. اتصال به کالا
  اختیاری است.
- رابط کاربری پیش‌نمایش مشخص نشان می‌دهد؛ مبلغ جزء، مالیات و جمع قطعی را سرور
  دوباره محاسبه و ذخیره می‌کند.
- فاکتوری که جمع قطعی آن صفر باشد رد می‌شود.
- یک بار فشردن ذخیره باید دقیقاً یک پیش‌نویس ایجاد کند. هنگام ارسال، دکمه برای
  جلوگیری از رکورد تکراری غیرفعال می‌شود.
- پس از موفقیت، پنجره بسته، فهرست تازه و پیام فارسی شامل شماره فاکتور نمایش داده
  می‌شود.
- در صورت خطا، اطلاعات واردشده باقی می‌مانند و خطای مشخص فارسی دیده می‌شود. فرم
  نباید ظاهراً هیچ واکنشی نداشته باشد.

#### رفتار پیش‌نویس

- پیش‌نویس فاکتور یک رکورد عملیاتی است، اما درآمد حسابداری ثبت‌شده نیست.
- ایجاد یا مشاهده پیش‌نویس نباید درآمد، مطالبات، تراز آزمایشی، سود و زیان یا جریان
  نقدی را تغییر دهد.
- پیش‌نویس پیش از صدور باید قابل بازبینی و در صورت پشتیبانی قابل ویرایش باشد.

#### صدور فاکتور

- صدور فقط با حساب‌های فعال دارای نقش صریح دریافتنی (`RECEIVABLE`) و درآمد
  (`REVENUE`) مجاز است؛ نوع کلی حساب به‌تنهایی کافی نیست. فاکتور دارای مالیات
  به حساب فعال بدهی مالیات (`TAX_LIABILITY`) نیز نیاز دارد.
- سند صدور، کل مبلغ را بدهکار دریافتنی، مبلغ جزء را بستانکار درآمد و مالیات
  غیرصفر را بستانکار بدهی مالیات می‌کند.

- صدور به مجوز مناسب، دوره باز و حساب‌های فعال دریافتنی و درآمد نیاز دارد.
- کاربر باید تأییدی ببیند که توضیح می‌دهد صدور، سند حسابداری ایجاد می‌کند.
- یک صدور موفق دقیقاً یک سند تراز ثبت‌شده می‌سازد، دریافتنی را بدهکار و درآمد را
  بستانکار می‌کند، وضعیت را به `ISSUED` تغییر می‌دهد و گزارش‌ها را فقط یک بار
  به‌روزرسانی می‌کند.
- کلیک تکراری، تازه‌سازی، تلاش دوباره یا صدور مجدد فاکتور صادرشده نباید سند
  تکراری بسازد یا اعداد داشبورد را دوباره افزایش دهد.
- سند ساخته‌شده از فاکتور نباید جداگانه برگشت داده شود و وضعیت فاکتور بدون تغییر
  بماند. اصلاح به فرایند مشخص ابطال یا یادداشت اعتباری نیاز دارد.

### ۸. فرایند دریافت وجه

- دریافت وجه به مشتری فعال و حداقل یک فاکتور صادرشده یا نیمه‌پرداخت‌شده با مانده
  باز برای همان مشتری نیاز دارد.
- تخصیص‌ها باید مثبت، متعلق به مشتری انتخابی، کمتر یا مساوی مانده فاکتور و در
  مجموع برابر مبلغ دریافت باشند.
- ذخیره، یک دریافت پیش‌نویس می‌سازد و جمع نقد ثبت‌شده را تغییر نمی‌دهد.
- ثبت نهایی باید سند تراز و تخصیص‌ها را اتمیک ایجاد کند؛ یا همه تغییرات موفق
  می‌شوند یا هیچ‌کدام.
- پرداخت کامل وضعیت فاکتور را `PAID` و پرداخت کمتر آن را `PARTIALLY_PAID` می‌کند.
- ثبت یا تلاش دوباره برای همان دریافت نباید آن را بیش از یک بار محاسبه کند.

### ۹. اسناد دستی و دوره‌های مالی

- سند دستی به شماره یکتا، تاریخ در دوره باز، شرح، حداقل دو ردیف معتبر و حساب‌های
  فعال نیاز دارد.
- هر ردیف فقط یک سمت و مقدار نامنفی دارد؛ جمع بدهکار و بستانکار باید برابر و
  بیشتر از صفر باشد.
- پیش‌نویس سند در گزارش‌ها اثر ندارد. ثبت نهایی اتمیک است و فقط یک بار اثر می‌گذارد.
- سند ثبت‌شده تغییرناپذیر است. برگشت معتبر یک سند ثبت‌شده معکوس می‌سازد و قابل
  تکرار نیست.
- بستن دوره باید هر ثبت جدید یا تغییر ثبت در آن دوره را متوقف کند.

### ۱۰. رفتار داشبورد

- داشبورد فقط خواندنی است و بارگذاری آن هرگز نباید در پایگاه داده بنویسد.
- مقادیر از رکوردهای ماندگار و ثبت‌شده تا یک تاریخ گزارش مشخص محاسبه می‌شوند.
- پیش‌نویس فاکتور، دریافت یا سند، مشاهده صفحه، تازه‌سازی مرورگر، بررسی سلامت و
  پیش‌بینی هوش مصنوعی نباید مبلغ مالی داشبورد را تغییر دهند.
- صدور یک فاکتور باید درآمد و مطالبات مربوط را دقیقاً یک بار افزایش دهد.
- ثبت یک دریافت باید جریان نقدی، مبلغ پرداخت‌شده و مانده مطالبات را دقیقاً یک بار
  تغییر دهد و درآمد جدید ایجاد نکند.
- اگر رکورد حسابداری تغییر نکرده باشد، دریافت دوباره داشبورد باید همان اعداد قبلی
  را برگرداند.
- کسب‌وکار خالی باید صفر یا حالت خالی نشان دهد، نه داده نمونه ساختگی.
- تعریف هر کارت داشبورد باید مشخص باشد و با گزارش متناظر تطبیق کند.

### ۱۱. گزارش‌ها

- تراز آزمایشی، سود و زیان، ترازنامه، درآمد، هزینه، مطالبات، پرداختنی‌ها، جریان
  نقدی و گردش طرف حساب فقط خواندنی هستند.
- گزارش‌ها فقط از رکورد ثبت‌شده استفاده می‌کنند؛ به‌جز نماهای عملیاتی که وضعیت
  فاکتور را آگاهانه نشان می‌دهند.
- فیلتر تاریخ و طرف حساب باید واضح، قطعی و اعتبارسنجی‌شده باشد.
- جمع گزارش‌ها باید با دفتر کل و کارت مرتبط داشبورد تطبیق کند.
- چاپ باید عنوان، فیلتر، تاریخ، برچسب ستون و جمع‌ها را حفظ کند.

### ۱۲. امکانات هوش مصنوعی

- طبقه‌بندی تراکنش، ریسک پرداخت، پیش‌بینی جریان نقدی و بخش‌بندی مشتری ابزار کمک
  به تصمیم هستند، نه ثبت حسابداری.
- اجرای پیش‌بینی می‌تواند رکورد قابل ممیزی ایجاد کند، اما نباید فاکتور، سند،
  پرداخت، مانده، درآمد یا اعداد داشبورد را تغییر دهد.
- نتیجه باید نسخه مدل فعال، عدم قطعیت یا اطمینان، توضیح فارسی و مقدار جایگزین امن
  داشته باشد.
- مدل و داده مصنوعی باید روشن علامت‌گذاری شوند و به‌عنوان دقت اثبات‌شده واقعی
  معرفی نشوند.

### ۱۳. خطا، بازخورد و پایداری

- فرم هنگام ارسال وضعیت در حال انجام نشان می‌دهد و ارسال تکراری را می‌بندد.
- موفقیت، اعتبارسنجی، تعارض، مجوز، ورود، سرور و شبکه پیام‌های فارسی مجزا دارند.
- عملیات حسابداری چندرکوردی ناموفق باید کاملاً برگشت داده شود.
- تازه‌سازی پس از عملیات باید وضعیت ماندگار سرور را نشان دهد.
- رمز، توکن، اطلاعات ورود و Secret نباید در لاگ، پیام رابط یا Git ثبت شوند.

### ۱۴. سناریوهای پذیرش مشکلات گزارش‌شده

#### ساخت فاکتور

۱. یک مشتری فعال، دوره مالی باز و حساب‌های فعال با نقش دریافتنی، درآمد و بدهی
مالیات ایجاد کنید.
۲. با کاربری دارای مجوز ساخت و صدور فاکتور وارد شوید.
۳. فاکتور `TEST-001` با یک قلم ۱۰۰ و مالیات ۱۰ بسازید.
۴. باید دقیقاً یک پیش‌نویس با جمع ۱۱۰ دیده شود.
۵. تا زمانی که پیش‌نویس است، داشبورد ثبت‌شده و گزارش‌ها نباید تغییر کنند.
۶. یک بار آن را صادر کنید؛ مطالبات باید ۱۱۰، درآمد ۱۰۰ و بدهی مالیات ۱۰ افزایش
یابد.
۷. مرورگر را چند بار تازه کنید؛ اعداد باید ثابت بمانند.
۸. صدور دوباره باید بدون سند یا مبلغ جدید رد شود.

#### ثبات داشبورد

۱. تمام اعداد داشبورد و تعداد رکوردهای پایگاه داده را ثبت کنید.
۲. داشبورد را ده بار تازه کنید و از صفحه خارج و دوباره وارد شوید.
۳. اعداد و تعداد رکوردها باید کاملاً یکسان بمانند.
۴. هر پیش‌بینی هوش مصنوعی را یک بار اجرا کنید؛ اعداد مالی داشبورد باید ثابت بمانند.
۵. فقط ثبت موفق عملیات حسابداری مجاز است کارت مالی مرتبط را تغییر دهد.

### ۱۵. مشکلات گزارش‌شده که منتظر تصمیم و پیاده‌سازی هستند

- کاربر گزارش کرده است که فاکتور جدید ساخته نمی‌شود. باید بازتولید شود تا مشخص
  شود علت، مجوز، پیش‌نیاز ناقص، رفتار ارسال رابط یا خطای API/دامنه است.
- کاربر گزارش کرده است که اعداد داشبورد پیوسته افزایش می‌یابند. مسیر هر کارت از
  رابط تا API گزارش و رکورد ماندگار باید بررسی شود؛ برای پنهان‌کردن علت نباید
  داده‌ای پاک یا Reset شود.
- برنامه نام IRANSans را در CSS دارد، اما فایل وب‌فونت دارای مجوز در مخزن نیست.
  برای تکمیل این نیاز باید فایل WOFF2 دارای مجوز فراهم و به‌صورت محلی میزبانی شود.

