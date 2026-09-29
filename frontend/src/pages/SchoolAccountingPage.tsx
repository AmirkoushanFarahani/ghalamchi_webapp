import { useMemo, useState } from "react";
import { DateField, DateText, EmptyState, ErrorState, LoadingState, Money, PageHeader, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api, query } from "../services/api";
import type { Payables, Student } from "../types/api";
import { Link } from "../routes/router";

interface ExpenseList { total: string; items: Array<{ id: string; factor_number: string; reason: string; amount: string; cost_date: string; payment_method: string }> }
interface StudentSegment { student_id: string; segment: number; behavioral_description: string; model_version: string; prediction_timestamp: string; as_of: string }
function Kpi({ title, value, tone = "" }: { title: string; value: string; tone?: string }) { return <article className={`kpi ${tone}`}><span>{title}</span><Money value={value} /></article>; }

export function SchoolAccountingPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [period, setPeriod] = useState({ start: "", end: "" });
  const state = useAsync(async () => {
    const [students, expenses, payables] = await Promise.all([
      api.get<Student[]>("/school/students"),
      api.get<ExpenseList>(query("/school/costs", { start_date: period.start, end_date: period.end })),
      api.get<Payables>("/reports/payables"),
    ]);
    return { students, expenses, payables };
  }, [period]);
  const [segments, setSegments] = useState<Record<string, StudentSegment>>({});
  const [segmentError, setSegmentError] = useState("");
  const [runningId, setRunningId] = useState<string | null>(null);
  const filteredStudents = useMemo(() => state.data?.students.filter((student) => (!period.start || student.registration_date >= period.start) && (!period.end || student.registration_date <= period.end)) ?? [], [period, state.data]);
  const totals = useMemo(() => {
    const enrollments = filteredStudents.flatMap((student) => student.enrollments);
    const billed = enrollments.reduce((sum, enrollment) => sum + Number(enrollment.total_amount), 0);
    const received = enrollments.reduce((sum, enrollment) => sum + Number(enrollment.amount_paid), 0);
    const receivable = enrollments.reduce((sum, enrollment) => sum + Number(enrollment.balance_due), 0);
    const expenses = Number(state.data?.expenses.total ?? 0);
    const payables = Number(state.data?.payables.total_payables ?? 0);
    return { billed, received, receivable, expenses, payables, net: received - expenses };
  }, [filteredStudents, state.data]);
  const records = useMemo(() => filteredStudents.flatMap((student) => student.enrollments.map((enrollment) => ({ student, enrollment }))), [filteredStudents]);
  const collections = useMemo(() => {
    const paid = records.flatMap((record) => record.enrollment.payments.filter((payment) => payment.status === "PAID"));
    const totalFor = (method: string) => paid.filter((payment) => payment.method === method).reduce((sum, payment) => sum + Number(payment.amount), 0);
    return { cash: totalFor("CASH"), transfer: totalFor("BANK_TRANSFER"), check: totalFor("CHECK"), installment: totalFor("INSTALLMENT") };
  }, [records]);
  const debtors = useMemo(() => records.filter((record) => Number(record.enrollment.balance_due) > 0).sort((a, b) => Number(b.enrollment.balance_due) - Number(a.enrollment.balance_due)), [records]);
  const dueItems = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    return records.flatMap((record) => record.enrollment.payments.filter((payment) => payment.status === "PENDING" && payment.due_date).map((payment) => ({ ...record, payment }))).sort((a, b) => (a.payment.due_date ?? "").localeCompare(b.payment.due_date ?? "")).filter((item) => (item.payment.due_date ?? "") <= today);
  }, [records]);
  const gradeSummary = useMemo(() => Object.entries(records.reduce<Record<string, { count: number; billed: number; paid: number; balance: number }>>((summary, { student, enrollment }) => {
    const row = summary[student.grade] ?? { count: 0, billed: 0, paid: 0, balance: 0 };
    row.count += 1; row.billed += Number(enrollment.total_amount); row.paid += Number(enrollment.amount_paid); row.balance += Number(enrollment.balance_due); summary[student.grade] = row; return summary;
  }, {})).sort(([first], [second]) => first.localeCompare(second)), [records]);
  const costByMethod = useMemo(() => {
    const totalFor = (method: string) => state.data?.expenses.items.filter((cost) => cost.payment_method === method).reduce((sum, cost) => sum + Number(cost.amount), 0) ?? 0;
    return { cash: totalFor("CASH"), transfer: totalFor("BANK_TRANSFER"), check: totalFor("CHECK") };
  }, [state.data]);
  async function cluster(student: Student) {
    setRunningId(student.id); setSegmentError("");
    try { const result = await api.post<StudentSegment>(`/school/accounting/students/${student.id}/segment`, {}); setSegments((current) => ({ ...current, [student.id]: result })); }
    catch (reason) { setSegmentError(reason instanceof Error ? reason.message : "اجرای بخش‌بندی هوشمند ناموفق بود."); }
    finally { setRunningId(null); }
  }
  if (state.loading) return <LoadingState />;
  if (state.error || !state.data) return <ErrorState message={state.error} retry={state.reload} />;
  const invalidPeriod = Boolean(startDate && endDate && startDate > endDate);
  return <><PageHeader title="حسابداری آموزشگاه" description="نمای مالی شهریه، هزینه‌ها، مطالبات و تحلیل دانش‌آموزان. این بخش فقط برای مدیر آموزشگاه است." action={<div className="button-row"><Link className="button button--secondary" to="/school-accounting/tuition">مطالبات شهریه</Link><Link className="button button--secondary" to="/school-accounting/cash-bank">صندوق و بانک</Link><Link className="button button--primary" to="/school-costs">ثبت هزینه</Link></div>} />
    <form className="form" onSubmit={(event) => { event.preventDefault(); if (!invalidPeriod) setPeriod({ start: startDate, end: endDate }); }}>
      <div className="form-grid form-grid--3"><DateField label="از تاریخ" value={startDate} onChange={setStartDate} /><DateField label="تا تاریخ" value={endDate} onChange={setEndDate} /><button className="button button--secondary" disabled={invalidPeriod}>نمایش گزارش دوره</button></div>
      {invalidPeriod && <p className="alert alert--error">تاریخ پایان باید بعد از تاریخ شروع باشد.</p>}
      {(period.start || period.end) && <button type="button" className="text-button" onClick={() => { setStartDate(""); setEndDate(""); setPeriod({ start: "", end: "" }); }}>پاک‌کردن فیلتر تاریخ</button>}
    </form>
    <section className="kpi-grid kpi-grid--3"><Kpi title="کل شهریه ثبت‌شده" value={totals.billed.toString()} tone="positive" /><Kpi title="شهریه دریافت‌شده" value={totals.received.toString()} tone="positive" /><Kpi title="مانده بدهی دانش‌آموزان" value={totals.receivable.toString()} tone={totals.receivable > 0 ? "negative" : "positive"} /><Kpi title="هزینه‌های ثبت‌شده" value={totals.expenses.toString()} /><Kpi title="بدهی به تأمین‌کنندگان" value={totals.payables.toString()} tone={totals.payables > 0 ? "negative" : "positive"} /><Kpi title="خالص دریافتی پس از هزینه" value={totals.net.toString()} tone={totals.net >= 0 ? "positive" : "negative"} /></section>
    <section className="card"><h2 className="card-title">راهنمای مانده‌ها</h2><div className="detail-grid"><p><strong>دانش‌آموزان بدهکار:</strong> شهریه‌ای که هنوز دریافت نشده است.</p><p><strong>بدهی به دیگران:</strong> صورتحساب‌های خرید صادرشده که هنوز پرداخت نشده‌اند.</p><p><strong>هزینه‌ها:</strong> پرداخت‌های هزینه‌ای که از بخش هزینه‌ها ثبت شده‌اند.</p></div></section>
    <section className="dashboard-grid">
      <section className="card"><h2 className="card-title">روش دریافت شهریه</h2><div className="detail-grid"><p>نقدی: <Money value={collections.cash.toString()} /></p><p>انتقال بانکی: <Money value={collections.transfer.toString()} /></p><p>چک وصول‌شده: <Money value={collections.check.toString()} /></p><p>اقساط وصول‌شده: <Money value={collections.installment.toString()} /></p></div></section>
      <section className="card"><h2 className="card-title">پیگیری فوری</h2>{dueItems.length ? <div className="compact-list">{dueItems.slice(0, 5).map(({ student, payment }) => <a key={payment.id} href={`/students/${student.id}`}><span><strong>{student.full_name}</strong><small>{payment.method === "CHECK" ? "چک" : "قسط"} · <DateText value={payment.due_date ?? ""} /></small></span><Money value={payment.amount} /></a>)}</div> : <EmptyState title="سررسید معوقی وجود ندارد" detail="چک یا قسط پرداخت‌نشده‌ای تا امروز ثبت نشده است." />}</section>
    </section>
    <section className="card"><h2 className="card-title">صندوق و بانک</h2><p className="form-description">این نما از پرداخت‌های ثبت‌شده و فاکتورهای هزینه ساخته می‌شود؛ چک‌های پرداخت‌نشده جزو موجودی قابل استفاده نیستند.</p><div className="detail-grid"><p>خالص نقدی: <Money value={(collections.cash - costByMethod.cash).toString()} /></p><p>خالص انتقال بانکی: <Money value={(collections.transfer - costByMethod.transfer).toString()} /></p><p>چک‌های وصول‌شده: <Money value={collections.check.toString()} /></p><p>هزینه‌های با چک: <Money value={costByMethod.check.toString()} /></p></div></section>
    <section className="card"><h2 className="card-title">مطالبات شهریه دانش‌آموزان</h2>{debtors.length ? <div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>پایه</th><th>کل شهریه</th><th>دریافت‌شده</th><th>مانده</th><th>وضعیت</th></tr></thead><tbody>{debtors.map(({ student, enrollment }) => <tr key={enrollment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{student.grade.replace("GRADE_", "پایه ")}</td><td><Money value={enrollment.total_amount} /></td><td><Money value={enrollment.amount_paid} /></td><td><Money value={enrollment.balance_due} /></td><td><StatusBadge value={enrollment.status} /></td></tr>)}</tbody></table></div> : <EmptyState title="مطالبه بازی وجود ندارد" detail="همه پرونده‌های ثبت‌شده تسویه شده‌اند." />}</section>
    <section className="card"><h2 className="card-title">خلاصه شهریه بر اساس پایه</h2>{gradeSummary.length ? <div className="table-wrap"><table><thead><tr><th>پایه</th><th>تعداد پرونده</th><th>شهریه ثبت‌شده</th><th>دریافتی</th><th>مانده</th></tr></thead><tbody>{gradeSummary.map(([grade, row]) => <tr key={grade}><td>{grade.replace("GRADE_", "پایه ")}</td><td>{row.count}</td><td><Money value={row.billed.toString()} /></td><td><Money value={row.paid.toString()} /></td><td><Money value={row.balance.toString()} /></td></tr>)}</tbody></table></div> : <EmptyState title="داده شهریه‌ای وجود ندارد" />}</section>
    <section className="card"><h2 className="card-title">آخرین هزینه‌های ثبت‌شده</h2>{state.data.expenses.items.length ? <div className="compact-list">{state.data.expenses.items.slice(0, 5).map((cost) => <a key={cost.id} href="/school-costs"><span><strong>{cost.reason}</strong><small>{cost.factor_number} · <DateText value={cost.cost_date} /></small></span><Money value={cost.amount} /></a>)}</div> : <EmptyState title="هزینه‌ای ثبت نشده است" detail="هزینه‌ها را از بخش هزینه‌های آموزشگاه ثبت کنید." />}</section>
    <section className="card"><h2 className="card-title">بخش‌بندی هوشمند دانش‌آموزان</h2><p className="form-description">مدل خوشه‌بندی با مبلغ شهریه، پرداخت‌ها، مانده، تعداد ثبت‌نام و نظم پرداخت همان دانش‌آموز کار می‌کند. این نتیجه فقط یک تحلیل کمکی است و هیچ مبلغ یا وضعیت مالی را تغییر نمی‌دهد.</p>{segmentError && <p className="alert alert--error">{segmentError}</p>}
      <div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>کل شهریه</th><th>پرداخت‌شده</th><th>مانده</th><th>وضعیت</th><th>تحلیل هوشمند</th></tr></thead><tbody>{state.data.students.map((student) => { const enrollment = student.enrollments[0]; const segment = segments[student.id]; return <tr key={student.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{enrollment ? <Money value={enrollment.total_amount} /> : "—"}</td><td>{enrollment ? <Money value={enrollment.amount_paid} /> : "—"}</td><td>{enrollment ? <Money value={enrollment.balance_due} /> : "—"}</td><td>{enrollment ? <StatusBadge value={enrollment.status} /> : "—"}</td><td>{segment ? <div><strong>گروه {segment.segment + 1}</strong><small>{segment.behavioral_description}</small><small>مدل {segment.model_version} · <DateText value={segment.as_of} /></small></div> : <button className="button button--secondary" disabled={runningId === student.id || !enrollment} onClick={() => void cluster(student)}>{runningId === student.id ? "در حال تحلیل…" : "تحلیل دانش‌آموز"}</button>}</td></tr>; })}</tbody></table></div>
    </section>
  </>;
}
