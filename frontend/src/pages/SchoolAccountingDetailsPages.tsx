import { useMemo, useState } from "react";
import { DateField, DateText, EmptyState, ErrorState, LoadingState, Money, PageHeader, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { Link } from "../routes/router";
import { api } from "../services/api";
import type { Student } from "../types/api";

interface SchoolCost { id: string; factor_number: string; reason: string; amount: string; cost_date: string; payment_method: "CASH" | "CHECK" | "BANK_TRANSFER"; check_due_date: string | null; vendor_name: string | null }
interface SchoolCostList { items: SchoolCost[]; total: string }
type RecordRow = { student: Student; enrollment: Student["enrollments"][number] };

const gradeLabel = (grade: string) => grade.replace("GRADE_", "پایه ");
const paymentLabel: Record<string, string> = { CASH: "نقدی", BANK_TRANSFER: "انتقال بانکی", CHECK: "چک", INSTALLMENT: "اقساط" };

function useFinanceData() {
  return useAsync(async () => {
    const [students, costs] = await Promise.all([api.get<Student[]>("/school/students"), api.get<SchoolCostList>("/school/costs")]);
    return { students, costs };
  }, []);
}

function Records({ students }: { students: Student[] }) {
  return students.flatMap((student) => student.enrollments.map((enrollment) => ({ student, enrollment })));
}

export function SchoolTuitionPage() {
  const state = useFinanceData();
  const [status, setStatus] = useState("OPEN");
  if (state.loading) return <LoadingState />;
  if (state.error || !state.data) return <ErrorState message={state.error} retry={state.reload} />;
  const finance = state.data;
  const records = Records({ students: finance.students });
  const visible = records.filter(({ enrollment }) => status === "ALL" || (status === "OPEN" && Number(enrollment.balance_due) > 0) || enrollment.status === status);
  const total = visible.reduce((sum, item) => sum + Number(item.enrollment.total_amount), 0);
  const paid = visible.reduce((sum, item) => sum + Number(item.enrollment.amount_paid), 0);
  const balance = visible.reduce((sum, item) => sum + Number(item.enrollment.balance_due), 0);
  return <>
    <PageHeader title="درآمد و مطالبات شهریه" description="تمام ثبت‌نام‌ها، مبلغ شهریه، دریافتی و مانده هر دانش‌آموز در یک گزارش قابل پیگیری." action={<Link className="button button--secondary" to="/school-accounting">بازگشت به نمای مالی</Link>} />
    <section className="kpi-grid kpi-grid--3"><Metric title="شهریه ثبت‌شده" value={total} tone="positive" /><Metric title="شهریه دریافت‌شده" value={paid} tone="positive" /><Metric title="مانده مطالبات" value={balance} tone={balance > 0 ? "negative" : "positive"} /></section>
    <section className="card"><div className="form-grid form-grid--3"><label className="field"><span>وضعیت پرونده</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="OPEN">دارای مانده</option><option value="ALL">همه پرونده‌ها</option><option value="PAID">تسویه‌شده</option><option value="UNPAID">پرداخت‌نشده</option><option value="PARTIALLY_PAID">پرداخت جزئی</option><option value="OVERDUE">سررسیدگذشته</option></select></label><div className="detail-grid"><p>تعداد پرونده: <strong>{visible.length}</strong></p></div></div></section>
    {visible.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>پایه</th><th>شهریه</th><th>دریافتی</th><th>مانده</th><th>وضعیت</th><th>پرونده</th></tr></thead><tbody>{visible.map(({ student, enrollment }) => <tr key={enrollment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{gradeLabel(student.grade)}</td><td><Money value={enrollment.total_amount} /></td><td><Money value={enrollment.amount_paid} /></td><td><Money value={enrollment.balance_due} /></td><td><StatusBadge value={enrollment.status} /></td><td><Link to={`/students/${student.id}`}>مشاهده</Link></td></tr>)}</tbody></table></div></section> : <EmptyState title="رکوردی با این وضعیت وجود ندارد" />}
  </>;
}

export function SchoolCashBankPage() {
  const state = useFinanceData();
  if (state.loading) return <LoadingState />;
  if (state.error || !state.data) return <ErrorState message={state.error} retry={state.reload} />;
  const finance = state.data;
  const records = Records({ students: finance.students });
  const paidPayments = records.flatMap(({ student, enrollment }) => enrollment.payments.filter((payment) => payment.status === "PAID").map((payment) => ({ student, payment })));
  const received = (method: string) => paidPayments.filter((item) => item.payment.method === method).reduce((sum, item) => sum + Number(item.payment.amount), 0);
  const costs = (method: string) => finance.costs.items.filter((item) => item.payment_method === method).reduce((sum, item) => sum + Number(item.amount), 0);
  const due = records.flatMap(({ student, enrollment }) => enrollment.payments.filter((payment) => payment.status === "PENDING" && payment.due_date).map((payment) => ({ student, payment }))).sort((a, b) => (a.payment.due_date ?? "").localeCompare(b.payment.due_date ?? ""));
  return <>
    <PageHeader title="صندوق و بانک" description="خلاصه مبالغ ثبت‌شده بر اساس روش دریافت و پرداخت. چک یا قسط پرداخت‌نشده جزو موجودی قابل استفاده نیست." action={<Link className="button button--secondary" to="/school-accounting">بازگشت به نمای مالی</Link>} />
    <section className="kpi-grid kpi-grid--3"><Metric title="خالص نقدی" value={received("CASH") - costs("CASH")} tone="positive" /><Metric title="خالص انتقال بانکی" value={received("BANK_TRANSFER") - costs("BANK_TRANSFER")} tone="positive" /><Metric title="چک‌های وصول‌شده" value={received("CHECK")} tone="positive" /><Metric title="اقساط وصول‌شده" value={received("INSTALLMENT")} tone="positive" /><Metric title="هزینه با چک" value={costs("CHECK")} /><Metric title="کل هزینه ثبت‌شده" value={Number(finance.costs.total)} /></section>
    <section className="dashboard-grid"><section className="card"><h2 className="card-title">دریافت‌های ثبت‌شده</h2>{paidPayments.length ? <div className="compact-list">{paidPayments.slice(0, 10).map(({ student, payment }) => <Link key={payment.id} to={`/students/${student.id}`}><span><strong>{student.full_name}</strong><small>{paymentLabel[payment.method]} · {payment.tracking_code ?? "بدون کد پیگیری"}</small></span><Money value={payment.amount} /></Link>)}</div> : <EmptyState title="دریافت ثبت‌شده‌ای وجود ندارد" />}</section><section className="card"><h2 className="card-title">چک‌ها و اقساط در انتظار وصول</h2>{due.length ? <div className="compact-list">{due.slice(0, 10).map(({ student, payment }) => <Link key={payment.id} to={`/students/${student.id}`}><span><strong>{student.full_name}</strong><small>{paymentLabel[payment.method]} · <DateText value={payment.due_date ?? ""} /></small></span><Money value={payment.amount} /></Link>)}</div> : <EmptyState title="چک یا قسط در انتظاری وجود ندارد" />}</section></section>
    <section className="card"><h2 className="card-title">پرداخت‌های هزینه</h2>{finance.costs.items.length ? <div className="table-wrap"><table><thead><tr><th>فاکتور</th><th>دلیل هزینه</th><th>تاریخ</th><th>روش</th><th>مبلغ</th></tr></thead><tbody>{finance.costs.items.map((cost) => <tr key={cost.id}><td dir="ltr">{cost.factor_number}</td><td>{cost.reason}</td><td><DateText value={cost.cost_date} /></td><td>{paymentLabel[cost.payment_method]}</td><td><Money value={cost.amount} /></td></tr>)}</tbody></table></div> : <EmptyState title="هزینه‌ای ثبت نشده است" detail="از بخش هزینه‌های آموزشگاه، فاکتور هزینه اضافه کنید." />}</section>
  </>;
}

export function SchoolReportPage() {
  const state = useFinanceData();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [range, setRange] = useState({ start: "", end: "" });
  if (state.loading) return <LoadingState />;
  if (state.error || !state.data) return <ErrorState message={state.error} retry={state.reload} />;
  const invalid = Boolean(start && end && start > end);
  const students = state.data.students.filter((student) => (!range.start || student.registration_date >= range.start) && (!range.end || student.registration_date <= range.end));
  const grouped = Object.entries(Records({ students }).reduce<Record<string, { count: number; billed: number; paid: number; balance: number }>>((summary, { student, enrollment }) => { const row = summary[student.grade] ?? { count: 0, billed: 0, paid: 0, balance: 0 }; row.count += 1; row.billed += Number(enrollment.total_amount); row.paid += Number(enrollment.amount_paid); row.balance += Number(enrollment.balance_due); summary[student.grade] = row; return summary; }, {})).sort(([first], [second]) => first.localeCompare(second));
  return <>
    <PageHeader title="گزارش شهریه بر اساس پایه" description="گزارش تعداد ثبت‌نام، شهریه، دریافتی و مانده برای هر پایه تحصیلی." action={<Link className="button button--secondary" to="/school-accounting">بازگشت به نمای مالی</Link>} />
    <form className="form" onSubmit={(event) => { event.preventDefault(); if (!invalid) setRange({ start, end }); }}><div className="form-grid form-grid--3"><DateField label="از تاریخ ثبت‌نام" value={start} onChange={setStart} /><DateField label="تا تاریخ ثبت‌نام" value={end} onChange={setEnd} /><button className="button button--secondary" disabled={invalid}>نمایش گزارش</button></div>{invalid && <p className="alert alert--error">تاریخ پایان باید بعد از تاریخ شروع باشد.</p>}</form>
    {grouped.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>پایه</th><th>تعداد دانش‌آموز</th><th>شهریه ثبت‌شده</th><th>دریافتی</th><th>مانده</th></tr></thead><tbody>{grouped.map(([grade, row]) => <tr key={grade}><td>{gradeLabel(grade)}</td><td>{row.count}</td><td><Money value={row.billed.toString()} /></td><td><Money value={row.paid.toString()} /></td><td><Money value={row.balance.toString()} /></td></tr>)}</tbody></table></div></section> : <EmptyState title="برای این بازه ثبت‌نامی وجود ندارد" />}
  </>;
}

function Metric({ title, value, tone = "" }: { title: string; value: number; tone?: string }) { return <article className={`kpi ${tone}`}><span>{title}</span><Money value={value.toString()} /></article>; }
