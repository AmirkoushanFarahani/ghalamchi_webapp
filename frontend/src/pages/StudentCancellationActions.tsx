import { useMemo, useState, type FormEvent } from "react";
import { DateField, Field, Modal, Money } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { Enrollment, EnrollmentCourse, ServiceCancellation, SpecialSupport, Student } from "../types/api";
import { todayIso } from "../utils/date";
import { PaymentPlanEditor, newPaymentPlan, paymentPlanPayload } from "../components/PaymentPlanEditor";

type CancelService = "COURSE" | "EXAM" | "BOOK" | "SUPPORT";
type Choice = { type: CancelService; course?: EnrollmentCourse; name: string; price: number; sessions: number };

export function activeServices(enrollment: Enrollment): Choice[] {
  const classes: Choice[] = enrollment.courses.filter((course) => course.status === "ACTIVE").map((course) => ({
    type: "COURSE" as const, course, name: `${course.course_name}${course.instructor_name ? ` — ${course.instructor_name}` : ""}`,
    price: Number(course.price), sessions: course.session_count,
  }));
  if (Number(enrollment.exam_price) > 0) classes.push({ type: "EXAM", name: `طرح آزمون (${enrollment.exam_session_count} آزمون)`, price: Number(enrollment.exam_price), sessions: enrollment.exam_session_count });
  if (Number(enrollment.book_price) > 0) classes.push({ type: "BOOK", name: "بن کتاب", price: Number(enrollment.book_price), sessions: 0 });
  if (Number(enrollment.special_support_price) > 0) classes.push({ type: "SUPPORT", name: enrollment.special_support_name || "پشتیبان ویژه", price: Number(enrollment.special_support_price), sessions: 0 });
  return classes;
}

export function ServiceCancellationModal({ student, enrollment, close, saved }: { student: Student; enrollment: Enrollment; close: () => void; saved: () => void }) {
  const choices = activeServices(enrollment); const [key, setKey] = useState(choices[0] ? `${choices[0].type}:${choices[0].course?.course_id ?? ""}` : "");
  const [reason, setReason] = useState(""); const [handling, setHandling] = useState<"CREDIT" | "REFUND">("CREDIT"); const [attendedSessions, setAttendedSessions] = useState("0"); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const selected = useMemo(() => choices.find((choice) => `${choice.type}:${choice.course?.course_id ?? ""}` === key), [choices, key]);
  const attended = Math.max(0, Number(attendedSessions || 0));
  const estimate = selected ? {
    attendance: selected.sessions ? selected.price * attended / selected.sessions : 0,
    fee: selected.price * .1,
  } : null;
  const retained = estimate ? Math.min(selected!.price, estimate.attendance + estimate.fee) : 0;
  const possibleRefund = Math.max(0, Math.min(Number(enrollment.amount_paid) - Math.max(0, Number(enrollment.total_amount) - selected!.price + retained), selected!.price - retained));
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (!selected) return; setBusy(true); setError("");
    try {
      await api.post<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/cancellations`, {
        service_type: selected.type, course_id: selected.course?.course_id ?? null, expected_original_price: selected.price.toFixed(2),
        expected_total: enrollment.total_amount, attended_sessions: attended, reason, excess_handling: handling,
      }); saved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "لغو خدمت ناموفق بود."); } finally { setBusy(false); }
  };
  return <Modal open title="لغو کامل خدمت و محاسبه بازپرداخت" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={(event) => void submit(event)}>
    {error && <div className="alert alert--error">{error}</div>}
    {!choices.length ? <p className="alert">خدمت فعالی برای لغو وجود ندارد.</p> : <>
      <Field label="خدمت یا محصول"><select value={key} onChange={(event) => { setKey(event.target.value); setAttendedSessions("0"); }}>{choices.map((choice) => <option key={`${choice.type}:${choice.course?.course_id ?? ""}`} value={`${choice.type}:${choice.course?.course_id ?? ""}`}>{choice.name}</option>)}</select></Field>
      {!!selected?.sessions && <Field label={`تعداد جلسات / آزمون‌های شرکت‌کرده از ${selected.sessions}`}><input type="number" min="0" max={selected.sessions} value={attendedSessions} onChange={(event) => setAttendedSessions(event.target.value)} required /></Field>}
      {selected && <div className="detail-grid"><p>مبلغ اولیه: <Money value={selected.price} /></p><p>جلسات حاضرشده: {attended} از {selected.sessions || "—"}</p><p>هزینه جلسات استفاده‌شده: <Money value={estimate?.attendance ?? 0} /></p><p>هزینه لغو (۱۰٪): <Money value={estimate?.fee ?? 0} /></p><p>مبلغ کسرشده از خدمت: <Money value={retained} /></p><p>بازپرداخت احتمالی: <Money value={possibleRefund} /></p></div>}
      <p className="muted">مبلغ نهایی در سرور و براساس فاکتور و پرداخت‌های واقعی محاسبه می‌شود. اگر همه جلسات استفاده شده باشند، بازپرداخت صفر است.</p>
      {selected?.type === "COURSE" && selected.sessions === 0 && <p className="alert alert--warning">تعداد جلسات کلاس هنوز توسط مدیر ثبت نشده است؛ ابتدا آن را در بخش کلاس‌ها وارد کنید.</p>}
      <Field label="انتخاب دانش‌آموز برای مبلغ اضافه"><select value={handling} onChange={(event) => setHandling(event.target.value as "CREDIT" | "REFUND")}><option value="CREDIT">ماندن به‌عنوان اعتبار دانش‌آموز</option><option value="REFUND">درخواست بازپرداخت با تأیید مدیر</option></select></Field>
      {enrollment.payments.some((payment) => payment.status === "PENDING") && <p className="alert alert--warning">چک‌ها و اقساط در انتظار، خودکار حذف یا کم نمی‌شوند. پس از لغو خدمت، برنامه پرداخت را بررسی و مورد جایگزین‌شده را جداگانه لغو کنید.</p>}
      <Field label="علت لغو"><input required value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} /></Field>
    </>}
    <div className="form-actions"><button className="button button--secondary" type="button" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy || !selected || (selected.type === "COURSE" && selected.sessions === 0)}>{busy ? "در حال ثبت…" : "تأیید لغو خدمت"}</button></div>
  </form></Modal>;
}

export function ServiceCancellationRefundModal({ student, enrollment, cancellation, close, saved }: { student: Student; enrollment: Enrollment; cancellation: ServiceCancellation; close: () => void; saved: () => void }) {
  const [action, setAction] = useState("PAY"); const [method, setMethod] = useState("BANK_TRANSFER"); const [paidOn, setPaidOn] = useState(todayIso()); const [tracking, setTracking] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setBusy(true); setError(""); try { await api.patch<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/cancellations/${cancellation.id}/refund`, { action, method: action === "PAY" ? method : null, paid_on: action === "PAY" ? paidOn : null, tracking_code: tracking || null }); saved(); } catch (failure) { setError(failure instanceof Error ? failure.message : "ثبت بازپرداخت ناموفق بود."); } finally { setBusy(false); } };
  return <Modal open title="تعیین تکلیف بازپرداخت لغو — مدیر" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={(event) => void submit(event)}>{error && <div className="alert alert--error">{error}</div>}<p>بازپرداخت {cancellation.service_name}: <Money value={cancellation.refund_amount} /></p><Field label="تصمیم"><select value={action} onChange={(event) => setAction(event.target.value)}><option value="PAY">پول واقعاً بازپرداخت شده است</option><option value="KEEP_CREDIT">لغو درخواست و حفظ اعتبار</option></select></Field>{action === "PAY" && <><Field label="روش بازپرداخت"><select value={method} onChange={(event) => setMethod(event.target.value)}><option value="BANK_TRANSFER">انتقال بانکی</option><option value="CASH">نقدی</option></select></Field><DateField label="تاریخ بازپرداخت" value={paidOn} onChange={setPaidOn} required /><Field label="کد پیگیری (اختیاری)"><input value={tracking} onChange={(event) => setTracking(event.target.value)} /></Field></>}<div className="form-actions"><button className="button button--secondary" type="button" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy}>{busy ? "در حال ثبت…" : "تأیید تصمیم"}</button></div></form></Modal>;
}

export function SpecialSupportChangeModal({ student, enrollment, close, saved }: { student: Student; enrollment: Enrollment; close: () => void; saved: () => void }) {
  const supports = useAsync(() => api.get<SpecialSupport[]>("/school/special-supports"), []);
  const [supportId, setSupportId] = useState(""); const [period, setPeriod] = useState<"MONTHLY" | "SEASONAL">("MONTHLY"); const [reason, setReason] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [plan, setPlan] = useState(newPaymentPlan); const [planValid, setPlanValid] = useState(false);
  const selected = (supports.data ?? []).find((support) => support.id === supportId && support.is_active);
  const newPrice = selected ? Number(period === "SEASONAL" ? selected.seasonal_price : selected.monthly_price) : 0;
  const newTotal = Math.max(0, Number(enrollment.subtotal) - Number(enrollment.special_support_price) + newPrice - Number(enrollment.discount_amount));
  const difference = newTotal - Number(enrollment.total_amount);
  const additionalDue = Math.max(newTotal - Math.max(Number(enrollment.total_amount), Number(enrollment.amount_paid)), 0);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!selected) return; setBusy(true); setError(""); try { await api.patch<Student>(`/school/students/${student.id}/enrollments/${enrollment.id}/special-support`, { support_id: selected.id, period, expected_old_price: enrollment.special_support_price, expected_total: enrollment.total_amount, reason, payment_plan: additionalDue > 0 ? paymentPlanPayload(plan, additionalDue) : null }); saved(); } catch (failure) { setError(failure instanceof Error ? failure.message : "تغییر پشتیبان ویژه ناموفق بود."); } finally { setBusy(false); } };
  return <Modal open title="تغییر پشتیبان ویژه" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={(event) => void submit(event)}>{error && <div className="alert alert--error">{error}</div>}{supports.loading ? <p>در حال دریافت فهرست پشتیبان‌ها…</p> : <><p>پشتیبان فعلی: <b>{enrollment.special_support_name || "ثبت نشده"}</b> · <Money value={enrollment.special_support_price} /></p><Field label="پشتیبان ویژه جدید"><select required value={supportId} onChange={(event) => setSupportId(event.target.value)}><option value="">انتخاب پشتیبان</option>{(supports.data ?? []).filter((support) => support.is_active).map((support) => <option key={support.id} value={support.id}>{support.name}</option>)}</select></Field><Field label="بازه پشتیبانی"><select value={period} onChange={(event) => setPeriod(event.target.value as "MONTHLY" | "SEASONAL")}><option value="MONTHLY">ماهانه</option><option value="SEASONAL">فصلی</option></select></Field>{selected && <div className="detail-grid"><p>مبلغ پشتیبان جدید: <Money value={newPrice} /></p><p>{difference >= 0 ? "افزایش شهریه" : "کاهش شهریه"}: <Money value={Math.abs(difference)} /></p><p>شهریه جدید پرونده: <Money value={newTotal} /></p></div>}<p className="muted">در صورت افزایش قیمت، مبلغ به مانده دانش‌آموز افزوده می‌شود. در صورت کاهش، اعتبار دانش‌آموز حفظ می‌شود؛ برای بازپرداخت واقعی می‌توانید ابتدا خدمت قبلی را لغو کنید.</p>{additionalDue > 0 && <PaymentPlanEditor total={additionalDue} value={plan} onChange={setPlan} disabled={busy} onValid={setPlanValid} />}<Field label="علت تغییر"><input required value={reason} maxLength={500} onChange={(event) => setReason(event.target.value)} /></Field></>}<div className="form-actions"><button className="button button--secondary" type="button" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy || !selected || (additionalDue > 0 && !planValid)}>{busy ? "در حال ذخیره…" : "تأیید تغییر پشتیبان"}</button></div></form></Modal>;
}
