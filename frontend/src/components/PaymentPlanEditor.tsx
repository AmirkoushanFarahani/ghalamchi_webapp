import { useEffect, useState } from "react";
import { DateField, DateText, Field, Money, MoneyInput } from "./ui";
import { request } from "../services/api";
import { todayIso } from "../utils/date";

export type PaymentPart = { amount: string; method: "CASH" | "BANK_TRANSFER" | "CHECK" | "INSTALLMENT"; due_date?: string | null; tracking_code?: string | null; sayad_id?: string | null };
type CheckDetails = { due_date?: string | null; tracking_code?: string | null; sayad_id?: string | null };
export type PaymentPlan = { items: PaymentPart[]; installment_count: number; installment_method?: "INSTALLMENT" | "CHECK"; check_details?: CheckDetails[] };
type Preview = { total: string; immediate: string; scheduled: string; items: PaymentPart[] };
type Mode = "FULL" | "INSTALLMENTS" | "ADVANCE";
export const paymentLabels = { CASH: "نقدی", BANK_TRANSFER: "انتقال بانکی", CHECK: "چک", INSTALLMENT: "قسط", MIXED: "ترکیبی" };
export const newPaymentPlan = (): PaymentPlan => ({ items: [{ amount: "", method: "CASH" }], installment_count: 0 });
export function paymentPlanPayload(plan: PaymentPlan, total: number | string): PaymentPlan {
  if (Number(total) === 0) return { items: [], installment_count: 0 };
  return { ...plan, items: plan.items.map((item) => ({ ...item, amount: item.amount || (plan.items.length === 1 && !plan.installment_count ? String(total) : "0") })) };
}

export function PaymentPlanEditor({ total, value, onChange, anchorDate = todayIso(), disabled = false, onValid }: {
  total: number | string; value: PaymentPlan; onChange: (value: PaymentPlan) => void;
  anchorDate?: string; disabled?: boolean; onValid?: (valid: boolean) => void;
}) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const mode: Mode = value.installment_count ? (value.items.length ? "ADVANCE" : "INSTALLMENTS") : "FULL";
  const payload = JSON.stringify({ total: String(total || 0), plan: paymentPlanPayload(value, total), anchor_date: anchorDate });
  useEffect(() => {
    let active = true; setLoading(true); onValid?.(false);
    const timeout = setTimeout(() => {
      void request<Preview>("/school/payment-plan/preview", { method: "POST", body: payload }).then((result) => {
        if (active) { setPreview(result); setError(""); setLoading(false); onValid?.(true); }
      }).catch((failure) => { if (active) { setPreview(null); setError(failure instanceof Error ? failure.message : "برنامه پرداخت معتبر نیست."); setLoading(false); onValid?.(false); } });
    }, 250);
    return () => { active = false; clearTimeout(timeout); };
  }, [payload]);
  const chooseMode = (next: Mode) => {
    onValid?.(false);
    onChange(next === "FULL" ? newPaymentPlan() : { items: next === "ADVANCE" ? [{ method: "CASH", amount: "" }] : [], installment_count: 3, installment_method: "INSTALLMENT", check_details: [] });
  };
  const updateImmediate = (fields: Partial<PaymentPart>) => onChange({ ...value, items: [{ ...value.items[0], ...fields }] });
  const updateCheck = (index: number, fields: CheckDetails) => {
    const details = Array.from({ length: value.installment_count }, (_, i) => value.check_details?.[i] ?? {});
    details[index] = { ...details[index], ...fields }; onChange({ ...value, check_details: details });
  };
  return <div className="payment-plan-editor">
    <p>مبلغ قابل پرداخت: <Money value={total || 0} /></p>
    <Field label="دانش‌آموز / مشتری چگونه پرداخت می‌کند؟"><select aria-label="نحوه پرداخت" value={mode} disabled={disabled} onChange={(e) => chooseMode(e.target.value as Mode)}>
      <option value="FULL">تمام مبلغ نقدی / انتقال بانکی</option>
      <option value="INSTALLMENTS">تمام مبلغ اقساطی</option>
      <option value="ADVANCE">پیش‌پرداخت نقدی + اقساط</option>
    </select></Field>
    {mode !== "INSTALLMENTS" && <div className="form-grid form-grid--2">
      <Field label={mode === "FULL" ? "روش پرداخت کامل" : "روش پیش‌پرداخت"}><select aria-label="روش پرداخت نقدی" value={value.items[0]?.method ?? "CASH"} disabled={disabled} onChange={(e) => updateImmediate({ method: e.target.value as PaymentPart["method"] })}><option value="CASH">نقدی</option><option value="BANK_TRANSFER">انتقال بانکی</option></select></Field>
      {mode === "ADVANCE" ? <Field label="مبلغ پیش‌پرداخت (تومان)"><MoneyInput aria-label="مبلغ پیش‌پرداخت" value={value.items[0]?.amount ?? ""} min="0.01" required disabled={disabled} onValueChange={(amount) => updateImmediate({ amount })} /></Field> : <p>مبلغ کامل: <Money value={total || 0} /></p>}
      <Field label="کد پیگیری پرداخت نقدی / بانکی (اختیاری)"><input disabled={disabled} value={value.items[0]?.tracking_code ?? ""} maxLength={100} onChange={(e) => updateImmediate({ tracking_code: e.target.value })} /></Field>
    </div>}
    {mode !== "FULL" && <>
      <div className="form-grid form-grid--2"><Field label="تعداد اقساط"><input aria-label="تعداد اقساط" type="number" min="1" max="60" step="1" value={value.installment_count} disabled={disabled} onChange={(e) => { const count = Math.max(1, Math.min(60, Math.trunc(Number(e.target.value) || 1))); onChange({ ...value, installment_count: count, check_details: value.check_details?.slice(0, count) }); }} /></Field>
      <Field label="نحوه پرداخت اقساط"><select aria-label="نحوه پرداخت اقساط" value={value.installment_method ?? "INSTALLMENT"} disabled={disabled} onChange={(e) => onChange({ ...value, installment_method: e.target.value as "CHECK" | "INSTALLMENT", check_details: [] })}><option value="INSTALLMENT">اقساط بدون چک</option><option value="CHECK">اقساط با چک</option></select></Field></div>
      <p className="muted">سامانه مانده را تقسیم می‌کند و تاریخ هر قسط را ماهانه شمسی تعیین می‌کند؛ اولین سررسید یک ماه پس از تاریخ فاکتور / ویرایش است.</p>
      {value.installment_method === "CHECK" && <><p className="muted">اطلاعات چک اختیاری است. اگر سررسید را وارد نکنید، تاریخ خودکار هر قسط استفاده می‌شود.</p>{Array.from({ length: value.installment_count }, (_, i) => <details key={i} className="card"><summary>اطلاعات اختیاری چک {i + 1}</summary>
        <DateField label={`سررسید چک ${i + 1} (اختیاری)`} value={value.check_details?.[i]?.due_date ?? ""} onChange={(due_date) => updateCheck(i, { due_date: due_date || null })} />
        <Field label="شناسه صیادی (اختیاری)"><input aria-label={`شناسه صیادی چک ${i + 1}`} value={value.check_details?.[i]?.sayad_id ?? ""} maxLength={32} disabled={disabled} onChange={(e) => updateCheck(i, { sayad_id: e.target.value })} /></Field>
        <Field label="کد پیگیری (اختیاری)"><input aria-label={`کد پیگیری چک ${i + 1}`} value={value.check_details?.[i]?.tracking_code ?? ""} maxLength={100} disabled={disabled} onChange={(e) => updateCheck(i, { tracking_code: e.target.value })} /></Field>
      </details>)}</>}
    </>}
    {loading && <p role="status">در حال محاسبه برنامه…</p>}
    {error && !loading && <p className="alert alert--error" role="alert">{error}</p>}
    {preview && !loading && <><div className="detail-grid"><p>پرداخت اکنون: <Money value={preview.immediate} /></p><p>مانده اقساط: <Money value={preview.scheduled} /></p></div>{mode !== "FULL" && <div className="table-wrap"><table><thead><tr><th>روش</th><th>مبلغ</th><th>سررسید</th></tr></thead><tbody>{preview.items.map((part, i) => <tr key={i}><td>{paymentLabels[part.method]}</td><td><Money value={part.amount} /></td><td>{part.due_date ? <DateText value={part.due_date} /> : "پرداخت اکنون"}</td></tr>)}</tbody></table></div>}</>}
  </div>;
}
