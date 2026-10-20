import { useState, type FormEvent } from "react";
import { DateField, ErrorState, Field, LoadingState, Modal, Money, MoneyInput } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { ClassChange, Course, Enrollment, EnrollmentCourse, EnrollmentPayment, Student } from "../types/api";
import { todayIso } from "../utils/date";

export function classChangeAmounts(enrollment: Enrollment, oldClass: EnrollmentCourse, replacement: Course) {
  const subtotal = Number(enrollment.subtotal) - Number(oldClass.price) + Number(replacement.price);
  const total = Math.max(subtotal - Number(enrollment.discount_amount), 0);
  const paid = Number(enrollment.amount_paid);
  return { total, difference: total - Number(enrollment.total_amount), additionalDue: Math.max(total - Math.max(Number(enrollment.total_amount), paid), 0), balance: Math.max(total - paid, 0), credit: Math.max(paid - total, 0) };
}

type Method = EnrollmentPayment["method"];
function PaymentFields({ method, setMethod, dueDate, setDueDate, tracking, setTracking, sayad, setSayad }: {
  method: Method; setMethod: (v: Method) => void; dueDate: string; setDueDate: (v: string) => void;
  tracking: string; setTracking: (v: string) => void; sayad: string; setSayad: (v: string) => void;
}) {
  return <><Field label="روش پرداخت"><select value={method} onChange={(e) => setMethod(e.target.value as Method)}><option value="CASH">نقدی</option><option value="BANK_TRANSFER">انتقال بانکی</option><option value="CHECK">چک</option><option value="INSTALLMENT">قسط</option></select></Field>
    {(method === "CHECK" || method === "INSTALLMENT") && <DateField label={method === "CHECK" ? "سررسید چک" : "سررسید قسط"} value={dueDate} onChange={setDueDate} required />}
    <Field label="کد پیگیری (اختیاری)"><input value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={100} /></Field>
    {method === "CHECK" && <Field label="شناسه صیادی (اختیاری)"><input value={sayad} onChange={(e) => setSayad(e.target.value)} maxLength={32} /></Field>}</>;
}

export function ClassChangeModal({ student, enrollment, oldClass, close, saved }: { student: Student; enrollment: Enrollment; oldClass: EnrollmentCourse; close: () => void; saved: () => void }) {
  const courses = useAsync(() => api.get<Course[]>(`/school/courses?grade=${student.grade}`), [student.grade]);
  const [selected, setSelected] = useState(""); const [reason, setReason] = useState("");
  const [handling, setHandling] = useState<"CREDIT" | "REFUND">("CREDIT"); const [collect, setCollect] = useState(false);
  const [method, setMethod] = useState<Method>("CASH"); const [dueDate, setDueDate] = useState(todayIso());
  const [tracking, setTracking] = useState(""); const [sayad, setSayad] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const available = (courses.data ?? []).filter((c) => c.is_active && !enrollment.courses.some((row) => row.course_id === c.id));
  const target = available.find((c) => c.id === selected); const amounts = target ? classChangeAmounts(enrollment, oldClass, target) : null;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!target || !amounts) return; setBusy(true); setError("");
    try {
      await api.patch<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/classes/${oldClass.course_id}`, {
        new_course_id: target.id, expected_old_price: oldClass.price, expected_new_price: target.price,
        expected_total: enrollment.total_amount, reason, excess_handling: handling,
        payment: collect && amounts.additionalDue > 0 ? { amount: amounts.additionalDue.toFixed(2), method, due_date: method === "CHECK" || method === "INSTALLMENT" ? dueDate : null, tracking_code: tracking || null, sayad_id: method === "CHECK" ? sayad || null : null } : null,
      }); saved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "تغییر کلاس ناموفق بود."); } finally { setBusy(false); }
  };
  return <Modal open title="تغییر کلاس / دبیر دانش‌آموز" onClose={() => { if (!busy) close(); }}>
    {courses.loading ? <LoadingState /> : courses.error ? <ErrorState message={courses.error} retry={courses.reload} /> : <form className="form" onSubmit={(e) => void submit(e)}>
      {error && <div className="alert alert--error" role="alert">{error}</div>}
      <p>{student.full_name} · کلاس فعلی: {oldClass.course_name} · <Money value={oldClass.price} /></p>
      <Field label="کلاس جایگزین (همان پایه و آموزشگاه)"><select required value={selected} onChange={(e) => { setSelected(e.target.value); setCollect(false); }}><option value="">انتخاب کلاس</option>{available.map((c) => <option key={c.id} value={c.id}>{c.name} · دبیر: {c.instructor_name || "ثبت نشده"} · {Number(c.price).toLocaleString("en-US", { maximumFractionDigits: 2 })} ریال</option>)}</select></Field>
      {!available.length && <p>کلاس فعال دیگری برای این پایه موجود نیست؛ مدیر باید ابتدا کلاس را تعریف کند.</p>}
      {amounts && <><div className="detail-grid"><p>شهریه جدید پرونده: <Money value={amounts.total} /></p><p>{amounts.difference >= 0 ? "افزایش شهریه" : "کاهش شهریه"}: <Money value={Math.abs(amounts.difference)} /></p><p>مابه‌التفاوت قابل پرداخت: <Money value={amounts.additionalDue} /></p><p>مانده قبل از پرداخت جدید: <Money value={amounts.balance} /></p><p>اعتبار پس از تغییر: <Money value={amounts.credit} /></p></div>
        <p className="muted">مبلغ تخفیف ثبت‌نام، خدمات آزمون و کتاب و پرداخت‌های قبلی حفظ می‌شوند. تأیید نهایی قیمت در سرور انجام می‌شود.</p>
        {amounts.additionalDue > 0 && <><Field label="پرداخت مابه‌التفاوت"><select value={collect ? "PAY" : "BALANCE"} onChange={(e) => setCollect(e.target.value === "PAY")}><option value="BALANCE">افزودن به مانده؛ دریافت بعداً</option><option value="PAY">ثبت پرداخت / چک / قسط اکنون</option></select></Field>{collect && <PaymentFields {...{ method, setMethod, dueDate, setDueDate, tracking, setTracking, sayad, setSayad }} />}</>}
        {amounts.credit > 0 && <><Field label="انتخاب دانش‌آموز برای اضافه‌پرداخت"><select value={handling} onChange={(e) => setHandling(e.target.value as "CREDIT" | "REFUND")}><option value="CREDIT">نگهداری اعتبار دانش‌آموز</option><option value="REFUND">درخواست بازپرداخت با تأیید مدیر</option></select></Field><p>اعتبار در همین پرونده ذخیره می‌شود. درخواست بازپرداخت تا ثبت پرداخت واقعی توسط مدیر، خروج پول محسوب نمی‌شود.</p></>}
        {enrollment.payments.some((p) => p.status === "PENDING") && <p className="alert">چک‌ها و اقساط قبلی خودکار تغییر نمی‌کنند؛ در صورت کاهش شهریه، برنامه قبلی را بررسی و موارد جایگزین‌شده را لغو کنید.</p>}
      </>}
      <Field label="علت تغییر کلاس" hint="توضیح کامل را بنویسید؛ حداکثر ۵۰۰ نویسه."><textarea value={reason} onChange={(e) => setReason(e.target.value)} required rows={4} maxLength={500} placeholder="مثلاً درخواست دانش‌آموز برای تغییر دبیر" /></Field>
      <div className="form-actions"><button type="button" className="button button--secondary" disabled={busy} onClick={close}>انصراف</button><button className="button button--primary" disabled={busy || !target}>{busy ? "در حال ثبت…" : "تأیید تغییر کلاس"}</button></div>
    </form>}
  </Modal>;
}

export function EnrollmentPaymentModal({ student, enrollment, close, saved }: { student: Student; enrollment: Enrollment; close: () => void; saved: () => void }) {
  const [amount, setAmount] = useState(String(enrollment.balance_due)); const [method, setMethod] = useState<Method>("CASH"); const [dueDate, setDueDate] = useState(todayIso());
  const [tracking, setTracking] = useState(""); const [sayad, setSayad] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await api.post<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/payments`, { amount, method, due_date: method === "CHECK" || method === "INSTALLMENT" ? dueDate : null, tracking_code: tracking || null, sayad_id: method === "CHECK" ? sayad || null : null }); saved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "ثبت پرداخت ناموفق بود."); } finally { setBusy(false); }
  };
  return <Modal open title="ثبت پرداخت مانده / مابه‌التفاوت" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={(e) => void submit(e)}>
    {error && <div className="alert alert--error" role="alert">{error}</div>}<p>مانده پرونده: <Money value={enrollment.balance_due} /></p>
    <Field label="مبلغ (ریال)"><MoneyInput value={amount} onValueChange={setAmount} min="0.01" max={enrollment.balance_due} required /></Field>
    <PaymentFields {...{ method, setMethod, dueDate, setDueDate, tracking, setTracking, sayad, setSayad }} />
    <p>اگر برای این مانده چک یا قسط قبلی ثبت شده، ابتدا آن را لغو کنید تا دوباره ثبت نشود.</p>
    <div className="form-actions"><button type="button" className="button button--secondary" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy}>{busy ? "در حال ثبت…" : "ثبت پرداخت"}</button></div>
  </form></Modal>;
}

export function RefundModal({ student, enrollment, change, close, saved }: { student: Student; enrollment: Enrollment; change: ClassChange; close: () => void; saved: () => void }) {
  const [action, setAction] = useState("PAY"); const [method, setMethod] = useState("BANK_TRANSFER"); const [paidOn, setPaidOn] = useState(todayIso()); const [tracking, setTracking] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await api.patch<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/refunds/${change.id}`, { action, method: action === "PAY" ? method : null, paid_on: action === "PAY" ? paidOn : null, tracking_code: tracking || null }); saved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "ثبت بازپرداخت ناموفق بود."); } finally { setBusy(false); }
  };
  return <Modal open title="تعیین تکلیف بازپرداخت — مدیر" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={(e) => void submit(e)}>
    {error && <div className="alert alert--error" role="alert">{error}</div>}<p>بازپرداخت به {student.full_name}: <Money value={change.refund_amount} /></p>
    <Field label="تصمیم با موافقت دانش‌آموز"><select value={action} onChange={(e) => setAction(e.target.value)}><option value="PAY">پول واقعاً بازپرداخت شده است</option><option value="KEEP_CREDIT">لغو درخواست و حفظ اعتبار</option></select></Field>
    {action === "PAY" && <><Field label="روش بازپرداخت"><select value={method} onChange={(e) => setMethod(e.target.value)}><option value="BANK_TRANSFER">انتقال بانکی</option><option value="CASH">نقدی</option></select></Field>
      <DateField label="تاریخ بازپرداخت واقعی" value={paidOn} onChange={setPaidOn} required /><Field label="کد پیگیری (اختیاری)"><input value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={100} /></Field><p className="alert">فقط پس از تحویل واقعی پول تأیید کنید. این سامانه انتقال بانکی انجام نمی‌دهد.</p></>}
    <div className="form-actions"><button type="button" className="button button--secondary" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy}>{busy ? "در حال ثبت…" : "تأیید تصمیم"}</button></div>
  </form></Modal>;
}
