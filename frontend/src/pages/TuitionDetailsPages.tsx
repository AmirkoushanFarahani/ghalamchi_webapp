import { useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { DateText, EmptyState, ErrorState, LoadingState, Modal, Money, PageHeader, StatusBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { Link } from "../routes/router";
import { api } from "../services/api";
import type { Enrollment, EnrollmentPayment, Student } from "../types/api";

type RecordRow = { student: Student; enrollment: Enrollment };
type PaymentRow = { student: Student; enrollment: Enrollment; payment: EnrollmentPayment };

const methodLabel: Record<EnrollmentPayment["method"], string> = {
  CASH: "نقدی",
  BANK_TRANSFER: "انتقال بانکی",
  CHECK: "چک",
  INSTALLMENT: "قسط",
};

function useStudents() {
  return useAsync(() => api.get<Student[]>("/school/students"), []);
}

function records(students: Student[]): RecordRow[] {
  return students.flatMap((student) =>
    student.enrollments.map((enrollment) => ({ student, enrollment })),
  );
}

function payments(rows: RecordRow[]): PaymentRow[] {
  return rows.flatMap(({ student, enrollment }) =>
    enrollment.payments.map((payment) => ({ student, enrollment, payment })),
  );
}

function BackToDashboard() {
  return <Link className="button button--secondary" to="/dashboard">بازگشت به داشبورد</Link>;
}

function PageState({ children }: { children: (students: Student[], reload: () => Promise<void>) => ReactNode }) {
  const state = useStudents();
  if (state.loading) return <LoadingState />;
  if (state.error || !state.data) return <ErrorState message={state.error} retry={state.reload} />;
  return <>{children(state.data, state.reload)}</>;
}

function EditPaymentsModal({ row, close, changed }: { row: RecordRow; close: () => void; changed: () => void }) {
  const [items, setItems] = useState<EnrollmentPayment[]>(row.enrollment.payments);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [touched, setTouched] = useState(false);
  const update = async (payment: EnrollmentPayment, status: "PAID" | "BOUNCED") => {
    setBusy(payment.id);
    setError("");
    try {
      const saved = await api.patch<EnrollmentPayment>(`/school/payments/${payment.id}`, { status });
      setItems((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setTouched(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "خطای ناشناخته");
    } finally {
      setBusy(null);
    }
  };
  const finish = () => { if (touched) changed(); close(); };
  return <Modal open title={`ویرایش وضعیت شهریه — ${row.student.full_name}`} onClose={finish} wide>
    {items.length ? <div className="table-wrap"><table><thead><tr><th>روش پرداخت</th><th>مبلغ</th><th>سررسید</th><th>وضعیت</th><th>تغییر وضعیت</th></tr></thead><tbody>{items.map((payment) => <tr key={payment.id}><td>{methodLabel[payment.method]}</td><td><Money value={payment.amount} /></td><td>{payment.due_date ? <DateText value={payment.due_date} /> : "—"}</td><td><StatusBadge value={payment.status} /></td><td>{payment.status === "PAID" ? "—" : <div className="button-row"><button className="button button--primary button--small" disabled={busy === payment.id} onClick={() => void update(payment, "PAID")}>وصول شد</button>{payment.status === "PENDING" && <button className="button button--secondary button--small" disabled={busy === payment.id} onClick={() => void update(payment, "BOUNCED")}>برگشت خورد</button>}</div>}</td></tr>)}</tbody></table></div> : <p>برای این پرونده پرداخت یا قسط ثبت‌شده‌ای وجود ندارد که وضعیت آن قابل تغییر باشد.</p>}
    <p><small>پرداخت وصول‌شده قابل تغییر نیست. با ثبت «وصول شد»، مبلغ دریافتی و مانده شهریه به‌طور خودکار به‌روز می‌شود.</small></p>
    {error && <p role="alert" className="negative">{error}</p>}
    <div className="form-actions"><button className="button button--secondary" onClick={finish}>بستن</button></div>
  </Modal>;
}

export function RegisteredTuitionPage() {
  return <PageState>{(students) => {
    const rows = records(students);
    const total = rows.reduce((sum, row) => sum + Number(row.enrollment.total_amount), 0);
    const collected = rows.reduce((sum, row) => sum + Number(row.enrollment.amount_paid), 0);
    return <>
      <PageHeader title="جزئیات شهریه‌های ثبت‌شده" description="فهرست کامل ثبت‌نام‌ها، مبلغ شهریه، تاریخ ثبت، وضعیت و مانده هر پرونده." action={<BackToDashboard />} />
      <section className="kpi-grid kpi-grid--3"><Metric title="تعداد پرونده‌ها" value={rows.length} count /><Metric title="جمع شهریه ثبت‌شده" value={total} tone="positive" /><Metric title="جمع دریافتی" value={collected} tone="positive" /></section>
      {rows.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>پایه</th><th>تاریخ ثبت</th><th>شهریه</th><th>دریافتی</th><th>مانده</th><th>وضعیت</th><th>پرونده</th></tr></thead><tbody>{rows.map(({ student, enrollment }) => <tr key={enrollment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{student.grade.replace("GRADE_", "پایه ")}</td><td><DateText value={student.registration_date} /></td><td><Money value={enrollment.total_amount} /></td><td><Money value={enrollment.amount_paid} /></td><td><Money value={enrollment.balance_due} /></td><td><StatusBadge value={enrollment.status} /></td><td><Link to={`/students/${student.id}`}>مشاهده</Link></td></tr>)}</tbody></table></div></section> : <EmptyState title="شهریه ثبت‌شده‌ای وجود ندارد" detail="پس از ثبت دانش‌آموز، پرونده او در این فهرست نمایش داده می‌شود." />}
    </>;
  }}</PageState>;
}

export function ReceivedTuitionPage() {
  return <PageState>{(students) => {
    const rows = payments(records(students)).filter(({ payment }) => payment.status === "PAID");
    const total = rows.reduce((sum, row) => sum + Number(row.payment.amount), 0);
    return <>
      <PageHeader title="جزئیات شهریه‌های دریافت‌شده" description="تمام پرداخت‌های وصول‌شده دانش‌آموزان، با روش، تاریخ ثبت یا وصول، مبلغ و وضعیت." action={<BackToDashboard />} />
      <section className="kpi-grid kpi-grid--2"><Metric title="جمع دریافتی" value={total} tone="positive" /><Metric title="تعداد پرداخت‌های وصول‌شده" value={rows.length} count /></section>
      {rows.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>روش پرداخت</th><th>مبلغ</th><th>تاریخ ثبت/وصول</th><th>سررسید</th><th>کد پیگیری</th><th>شناسه صیادی</th><th>وضعیت</th><th>پرونده</th></tr></thead><tbody>{rows.map(({ student, payment }) => <tr key={payment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{methodLabel[payment.method]}</td><td><Money value={payment.amount} /></td><td><DateText value={payment.updated_at} /></td><td>{payment.due_date ? <DateText value={payment.due_date} /> : "—"}</td><td dir="ltr">{payment.tracking_code || "—"}</td><td dir="ltr">{payment.sayad_id || "—"}</td><td><StatusBadge value={payment.status} /></td><td><Link to={`/students/${student.id}`}>مشاهده</Link></td></tr>)}</tbody></table></div></section> : <EmptyState title="دریافتی وصول‌شده‌ای وجود ندارد" />}
    </>;
  }}</PageState>;
}

export function OutstandingTuitionPage() {
  const { can } = useAuth();
  const [editing, setEditing] = useState<RecordRow | null>(null);
  const canEdit = can("school:payments");
  return <PageState>{(students, reload) => {
    const rows = records(students).filter(({ enrollment }) => Number(enrollment.balance_due) > 0).sort((a, b) => Number(b.enrollment.balance_due) - Number(a.enrollment.balance_due));
    const total = rows.reduce((sum, row) => sum + Number(row.enrollment.balance_due), 0);
    return <>
      <PageHeader title="جزئیات مانده شهریه دانش‌آموزان" description="پرونده‌های دارای مانده، مبلغ باقی‌مانده، وضعیت و نزدیک‌ترین سررسید پرداخت." action={<BackToDashboard />} />
      <section className="kpi-grid kpi-grid--2"><Metric title="جمع مانده شهریه" value={total} tone={total ? "negative" : "positive"} /><Metric title="پرونده‌های باز" value={rows.length} count /></section>
      {rows.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>پایه</th><th>شهریه کل</th><th>دریافتی</th><th>مانده</th><th>نزدیک‌ترین سررسید</th><th>وضعیت</th>{canEdit && <th>ویرایش</th>}<th>پرونده</th></tr></thead><tbody>{rows.map(({ student, enrollment }) => { const nextDue = enrollment.payments.filter((payment) => payment.status === "PENDING" && payment.due_date).sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""))[0]; return <tr key={enrollment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{student.grade.replace("GRADE_", "پایه ")}</td><td><Money value={enrollment.total_amount} /></td><td><Money value={enrollment.amount_paid} /></td><td><Money value={enrollment.balance_due} /></td><td>{nextDue ? <DateText value={nextDue.due_date} /> : "بدون سررسید"}</td><td><StatusBadge value={enrollment.status} /></td>{canEdit && <td><button className="button button--secondary button--small" onClick={() => setEditing({ student, enrollment })}>ویرایش</button></td>}<td><Link to={`/students/${student.id}`}>مشاهده</Link></td></tr>; })}</tbody></table></div></section> : <EmptyState title="همه شهریه‌ها تسویه شده‌اند" />}
      {editing && <EditPaymentsModal key={editing.enrollment.id} row={editing} close={() => setEditing(null)} changed={() => void reload()} />}
    </>;
  }}</PageState>;
}

export function DuePaymentsPage() {
  return <PageState>{(students) => {
    const today = new Date().toISOString().slice(0, 10);
    const rows = payments(records(students)).filter(({ payment }) => (payment.method === "CHECK" || payment.method === "INSTALLMENT") && payment.status === "PENDING" && payment.due_date && payment.due_date <= today).sort((a, b) => (a.payment.due_date ?? "").localeCompare(b.payment.due_date ?? ""));
    const total = rows.reduce((sum, row) => sum + Number(row.payment.amount), 0);
    return <>
      <PageHeader title="اقساط و چک‌های سررسیدشده" description="موارد پرداخت‌نشده‌ای که تاریخ سررسیدشان رسیده یا گذشته است و به پیگیری نیاز دارند." action={<BackToDashboard />} />
      <section className="kpi-grid kpi-grid--2"><Metric title="مبلغ نیازمند پیگیری" value={total} tone={rows.length ? "negative" : "positive"} /><Metric title="تعداد موارد سررسیدشده" value={rows.length} count /></section>
      {rows.length ? <section className="card"><div className="table-wrap"><table><thead><tr><th>دانش‌آموز</th><th>نوع</th><th>مبلغ</th><th>سررسید</th><th>وضعیت</th><th>پیگیری</th><th>شناسه/کد پیگیری</th><th>پرونده</th></tr></thead><tbody>{rows.map(({ student, payment }) => <tr key={payment.id}><td><strong>{student.full_name}</strong><small>{student.guardian_full_name}</small></td><td>{methodLabel[payment.method]}</td><td><Money value={payment.amount} /></td><td><DateText value={payment.due_date} /></td><td><StatusBadge value={payment.status} /></td><td><span className="badge badge--danger">نیازمند پیگیری</span></td><td dir="ltr">{payment.method === "CHECK" ? payment.sayad_id || "—" : payment.tracking_code || "—"}</td><td><Link to={`/students/${student.id}`}>مشاهده</Link></td></tr>)}</tbody></table></div></section> : <EmptyState title="سررسید پرداخت‌نشده‌ای وجود ندارد" detail="چک یا قسطی که به پیگیری نیاز داشته باشد، در این بخش نمایش داده می‌شود." />}
    </>;
  }}</PageState>;
}

function Metric({ title, value, tone = "", count = false }: { title: string; value: number; tone?: string; count?: boolean }) {
  return <article className={`kpi ${tone}`}><span>{title}</span>{count ? <strong>{value}</strong> : <Money value={value} />}</article>;
}
