import { useState, type FormEvent } from "react";
import { DateField, DateText, EmptyState, ErrorState, Field, LoadingState, Modal, Money, MoneyInput, PageHeader, StatusBadge } from "../components/ui";
import { PaymentPlanEditor, newPaymentPlan, paymentLabels, paymentPlanPayload } from "../components/PaymentPlanEditor";
import { useAsync } from "../hooks/useAsync";
import { api, query } from "../services/api";
import { todayIso } from "../utils/date";
import type { EnrollmentPayment } from "../types/api";

export interface SchoolCost { id: string; factor_number: string; vendor_name: string | null; reason: string; amount: string; amount_paid: string; balance_due: string; cost_date: string; payment_method: string; check_due_date: string | null; tracking_code: string | null; notes: string | null; payments: EnrollmentPayment[] }
export interface SchoolCostList { items: SchoolCost[]; total: string; total_paid: string; total_outstanding: string }

export function SchoolCostsPage() {
  const [open, setOpen] = useState(false); const [editing, setEditing] = useState<SchoolCost | null>(null);
  const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [range, setRange] = useState({ start: "", end: "" });
  const state = useAsync(() => api.get<SchoolCostList>(query("/school/costs", { start_date: range.start, end_date: range.end })), [range]);
  return <><PageHeader title="هزینه‌های آموزشگاه" description="ثبت فاکتور هزینه، پرداخت ترکیبی و پیگیری بدهی به فروشنده یا دریافت‌کننده." action={<button className="button button--primary" onClick={() => setOpen(true)}>ثبت هزینه جدید</button>} />
    <form className="form" onSubmit={(e) => { e.preventDefault(); setRange({ start, end }); }}><div className="form-grid form-grid--3"><DateField label="از تاریخ" value={start} onChange={setStart} /><DateField label="تا تاریخ" value={end} onChange={setEnd} /><button className="button button--secondary" disabled={!!start && !!end && start > end}>نمایش هزینه‌ها</button></div></form>
    {state.loading ? <LoadingState /> : state.error ? <ErrorState message={state.error} retry={state.reload} /> : <>
      <section className="kpi-grid kpi-grid--3"><article className="kpi"><span>هزینه ثبت‌شده</span><Money value={state.data?.total ?? "0"} /></article><article className="kpi"><span>واقعاً پرداخت‌شده</span><Money value={state.data?.total_paid ?? "0"} /></article><article className="kpi"><span>بدهی بابت هزینه‌ها</span><Money value={state.data?.total_outstanding ?? "0"} /></article></section>
      {state.data?.items.length ? <div className="table-wrap"><table><thead><tr><th>فاکتور</th><th>دلیل هزینه / دریافت‌کننده</th><th>تاریخ</th><th>کل</th><th>پرداخت‌شده</th><th>بدهی</th><th>روش</th><th>عملیات</th></tr></thead><tbody>{state.data.items.map((cost) => <tr key={cost.id}><td>{cost.factor_number}</td><td>{cost.reason}<small>{cost.vendor_name ?? "—"}</small><small>{cost.notes ?? ""}</small></td><td><DateText value={cost.cost_date} /></td><td><Money value={cost.amount} /></td><td><Money value={cost.amount_paid} /></td><td><Money value={cost.balance_due} /></td><td>{paymentLabels[cost.payment_method as keyof typeof paymentLabels] ?? cost.payment_method}</td><td><button className="button button--secondary button--small" onClick={() => setEditing(cost)}>پرداخت‌ها / برنامه مانده</button></td></tr>)}</tbody></table></div> : <EmptyState title="فاکتور هزینه‌ای ثبت نشده است" />}
    </>}
    {open && <SchoolCostForm close={() => setOpen(false)} saved={() => { setOpen(false); void state.reload(); }} />}
    {editing && <CostPaymentsModal initial={editing} close={() => setEditing(null)} changed={() => void state.reload()} />}
  </>;
}

function SchoolCostForm({ close, saved }: { close: () => void; saved: () => void }) {
  const [amount, setAmount] = useState(""); const [date, setDate] = useState(todayIso());
  const [plan, setPlan] = useState(newPaymentPlan); const [valid, setValid] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy || !valid) return;
    const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try { await api.post("/school/costs", { factor_number: form.get("factor_number") || null, vendor_name: form.get("vendor_name") || null, reason: form.get("reason"), amount, cost_date: date, notes: form.get("notes") || null, payment_plan: paymentPlanPayload(plan, amount) }); saved(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "ثبت فاکتور هزینه ناموفق بود."); } finally { setBusy(false); }
  }
  return <Modal open wide title="ثبت فاکتور هزینه" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={submit}>
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    <Field label="شماره فاکتور (اختیاری؛ در صورت خالی بودن خودکار)"><input name="factor_number" maxLength={100} disabled={busy} /></Field>
    <Field label="دلیل هزینه"><input name="reason" maxLength={300} required disabled={busy} /></Field>
    <Field label="فروشنده / دریافت‌کننده (اختیاری)"><input name="vendor_name" maxLength={200} disabled={busy} /></Field>
    <Field label="مبلغ کل (تومان)"><MoneyInput value={amount} onValueChange={setAmount} min="0.01" required disabled={busy} /></Field>
    <DateField label="تاریخ فاکتور هزینه" value={date} onChange={setDate} required />
    <PaymentPlanEditor total={amount} value={plan} onChange={setPlan} anchorDate={date} disabled={busy} onValid={setValid} />
    <Field label="یادداشت (اختیاری)"><textarea name="notes" maxLength={1000} disabled={busy} /></Field>
    <div className="form-actions"><button type="button" className="button button--secondary" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy || !valid || Number(amount) <= 0}>{busy ? "در حال ذخیره…" : "ثبت فاکتور هزینه"}</button></div>
  </form></Modal>;
}

function CostPaymentsModal({ initial, close, changed }: { initial: SchoolCost; close: () => void; changed: () => void }) {
  const [cost, setCost] = useState(initial); const [edit, setEdit] = useState(false);
  const [plan, setPlan] = useState(newPaymentPlan); const [valid, setValid] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function settle(payment: EnrollmentPayment, status: "PAID" | "BOUNCED") {
    setBusy(true); setError("");
    try { setCost(await api.patch<SchoolCost>(`/school/costs/${cost.id}/payments/${payment.id}`, { status })); setEdit(false); changed(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "تغییر وضعیت ناموفق بود."); } finally { setBusy(false); }
  }
  async function replace(event: FormEvent) {
    event.preventDefault(); if (busy || !valid) return; setBusy(true); setError("");
    try { setCost(await api.put<SchoolCost>(`/school/costs/${cost.id}/payment-plan`, { plan: paymentPlanPayload(plan, cost.balance_due), expected_balance: cost.balance_due, expected_pending_ids: cost.payments.filter((p) => p.status === "PENDING" || p.status === "BOUNCED").map((p) => p.id) })); setEdit(false); changed(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "ذخیره برنامه ناموفق بود."); } finally { setBusy(false); }
  }
  return <Modal open wide title={`پرداخت‌های هزینه — ${cost.factor_number}`} onClose={() => { if (!busy) close(); }}>
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    <p>بدهی باقی‌مانده: <Money value={cost.balance_due} /></p>
    <div className="table-wrap"><table><thead><tr><th>روش</th><th>مبلغ</th><th>سررسید</th><th>کد پیگیری / صیادی</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{cost.payments.map((payment) => <tr key={payment.id}><td>{paymentLabels[payment.method]}</td><td><Money value={payment.amount} /></td><td><DateText value={payment.due_date} /></td><td>{payment.tracking_code ?? "—"}<small>{payment.sayad_id ?? ""}</small></td><td><StatusBadge value={payment.status} /></td><td>{(payment.status === "PENDING" || payment.status === "BOUNCED") && <div className="button-row"><button className="button button--secondary button--small" disabled={busy} onClick={() => void settle(payment, "PAID")}>واقعاً پرداخت شد</button>{payment.method === "CHECK" && payment.status === "PENDING" && <button className="button button--secondary button--small" disabled={busy} onClick={() => void settle(payment, "BOUNCED")}>برگشت چک</button>}</div>}</td></tr>)}</tbody></table></div>
    {Number(cost.balance_due) > 0 && <button type="button" className="button button--secondary" disabled={busy} onClick={() => setEdit(!edit)}>ویرایش برنامه پرداخت‌نشده</button>}
    {edit && <form className="form" onSubmit={replace}><p className="alert">پرداخت‌های قطعی تغییر نمی‌کنند؛ فقط بخش‌های پرداخت‌نشده جایگزین می‌شوند.</p><PaymentPlanEditor total={cost.balance_due} value={plan} onChange={setPlan} disabled={busy} onValid={setValid} /><button className="button button--primary" disabled={busy || !valid}>ذخیره برنامه مانده</button></form>}
  </Modal>;
}
