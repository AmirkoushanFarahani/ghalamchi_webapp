import { useState, type FormEvent } from "react";
import { DateText, EmptyState, ErrorState, LoadingState, Modal } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { SchoolInstitute } from "../types/api";

interface Secretary {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  is_active: boolean;
  last_login_at: string | null;
}
type Action = "create" | "edit" | "password" | "dismiss" | "restore";

export function SchoolSecretariesPanel({ school }: { school: SchoolInstitute }) {
  const base = `/school/institutes/${school.id}/secretaries`;
  const state = useAsync(() => api.get<Secretary[]>(base), [school.id]);
  const [action, setAction] = useState<Action | null>(null);
  const [selected, setSelected] = useState<Secretary | null>(null);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "", confirmation: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const titles: Record<Action, string> = {
    create: "افزودن منشی", edit: "ویرایش اطلاعات و ایمیل ورود",
    password: "تغییر رمز عبور", dismiss: "قطع دسترسی منشی", restore: "فعال‌سازی مجدد منشی",
  };
  function open(next: Action, secretary: Secretary | null = null) {
    setAction(next); setSelected(secretary); setError(""); setSuccess("");
    setForm({ first_name: secretary?.first_name ?? "", last_name: secretary?.last_name ?? "",
      email: secretary?.email ?? "", password: "", confirmation: "" });
  }
  function close() {
    if (busy) return;
    setAction(null); setSelected(null);
    setForm({ first_name: "", last_name: "", email: "", password: "", confirmation: "" });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!action) return;
    setError("");
    if ((action === "create" || action === "password") && form.password !== form.confirmation) {
      setError("رمز عبور و تکرار آن یکسان نیستند."); return;
    }
    setBusy(true);
    try {
      if (action === "create") {
        await api.post(base, { first_name: form.first_name.trim(), last_name: form.last_name.trim(),
          email: form.email.trim(), password: form.password });
      } else if (selected) {
        if (action === "edit") await api.patch(`${base}/${selected.id}`, {
          first_name: form.first_name.trim(), last_name: form.last_name.trim(), email: form.email.trim(),
        });
        if (action === "password") await api.patch(`${base}/${selected.id}/password`, { password: form.password });
        if (action === "dismiss" || action === "restore") await api.patch(`${base}/${selected.id}/status`, { is_active: action === "restore" });
      }
      setAction(null); setSelected(null);
      setForm({ first_name: "", last_name: "", email: "", password: "", confirmation: "" });
      setSuccess("تغییرات منشی ذخیره شد."); await state.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ذخیره تغییرات ناموفق بود."); }
    finally { setBusy(false); }
  }
  return <section className="card">
    <div className="button-row"><h2 className="card-title">منشی‌های {school.name}</h2>
      <button className="button button--primary" onClick={() => open("create")}>افزودن منشی جدید</button>
    </div>
    {success && <p role="status">{success}</p>}
    {state.loading ? <LoadingState /> : state.error ? <ErrorState message={state.error} retry={state.reload} /> : !state.data?.length ? <EmptyState title="هنوز منشی برای این مرکز ثبت نشده است" /> :
      <div className="table-wrap"><table><thead><tr><th>نام و نام خانوادگی</th><th>ایمیل ورود</th><th>وضعیت دسترسی</th><th>آخرین ورود</th><th>عملیات</th></tr></thead><tbody>
        {state.data.map((secretary) => <tr key={secretary.id}>
          <td>{secretary.first_name} {secretary.last_name}</td><td dir="ltr">{secretary.email ?? "—"}</td>
          <td>{secretary.is_active ? "فعال" : "قطع دسترسی"}</td>
          <td>{secretary.last_login_at ? <DateText value={secretary.last_login_at} /> : "هنوز وارد نشده است"}</td>
          <td><div className="button-row">
            <button className="button button--secondary" disabled={busy} onClick={() => open("edit", secretary)}>ویرایش اطلاعات ورود</button>
            <button className="button button--secondary" disabled={busy} onClick={() => open("password", secretary)}>تغییر رمز عبور</button>
            <button className="button button--secondary" disabled={busy} onClick={() => open(secretary.is_active ? "dismiss" : "restore", secretary)}>{secretary.is_active ? "قطع دسترسی" : "فعال‌سازی مجدد"}</button>
          </div></td>
        </tr>)}
      </tbody></table></div>}
    {action && <Modal open title={`${titles[action]} — ${school.name}`} onClose={close}>
      <form className="form" onSubmit={save}>
        {selected && <p>{selected.first_name} {selected.last_name}</p>}
        {(action === "create" || action === "edit") && <>
          <label>نام<input required maxLength={100} disabled={busy} value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></label>
          <label>نام خانوادگی<input required maxLength={100} disabled={busy} value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></label>
          <label>ایمیل ورود<input required type="email" dir="ltr" disabled={busy} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        </>}
        {(action === "create" || action === "password") && <>
          <label>رمز عبور جدید<input required type="password" dir="ltr" autoComplete="new-password" minLength={12} maxLength={128} disabled={busy} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <label>تکرار رمز عبور<input required type="password" dir="ltr" autoComplete="new-password" minLength={12} maxLength={128} disabled={busy} value={form.confirmation} onChange={(e) => setForm({ ...form, confirmation: e.target.value })} /></label>
          <p>رمز عبور باید حداقل ۱۲ نویسه داشته باشد.</p>
        </>}
        {action === "dismiss" && <p>دسترسی این منشی به سامانه قطع می‌شود. سوابق دانش‌آموزان و پرداخت‌های ثبت‌شده حفظ می‌شوند.</p>}
        {action === "restore" && <p>دسترسی منشی به همین مرکز دوباره فعال می‌شود.</p>}
        {error && <p className="alert alert--error" role="alert">{error}</p>}
        <div className="button-row"><button className="button button--primary" disabled={busy}>{busy ? "در حال ذخیره…" : "تأیید و ذخیره"}</button><button type="button" className="button button--secondary" disabled={busy} onClick={close}>انصراف</button></div>
      </form>
    </Modal>}
  </section>;
}
