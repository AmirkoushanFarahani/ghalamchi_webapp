import { useState } from "react";
import { ErrorState, LoadingState, Money, PageHeader } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { SchoolComparison, SchoolInstitute } from "../types/api";

export function SchoolInstitutesPage() {
  const data = useAsync(async () => {
    const [institutes, comparison] = await Promise.all([
      api.get<SchoolInstitute[]>("/school/institutes"),
      api.get<SchoolComparison[]>("/school/institutes/comparison"),
    ]);
    return { institutes, comparison };
  }, []);
  const [name, setName] = useState("");
  const [secretaryFor, setSecretaryFor] = useState<string | null>(null);
  const [secretary, setSecretary] = useState({ first_name: "", last_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function create(event: React.FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await api.post("/school/institutes", { name }); setName(""); await data.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "ثبت مرکز ناموفق بود."); }
    finally { setBusy(false); }
  }
  async function activate(id: string) {
    setError(""); setBusy(true);
    try { await api.patch("/school/institutes/active", { school_institute_id: id }); window.location.assign("/dashboard"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "تغییر مرکز ناموفق بود."); setBusy(false); }
  }
  async function createSecretary(event: React.FormEvent) {
    event.preventDefault(); if (!secretaryFor) return; setError(""); setBusy(true);
    try { await api.post(`/school/institutes/${secretaryFor}/secretaries`, secretary); setSecretaryFor(null); setSecretary({ first_name: "", last_name: "", email: "", password: "" }); await data.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "ساخت حساب منشی ناموفق بود."); }
    finally { setBusy(false); }
  }
  if (data.loading) return <LoadingState />;
  if (data.error || !data.data) return <ErrorState message={data.error} retry={data.reload} />;
  return <><PageHeader title="مدیریت مراکز آموزشی" description="هر مدیر می‌تواند حداکثر دو مدرسه یا آموزشگاه مستقل داشته باشد. دانش‌آموزان، شهریه‌ها و هزینه‌های هر مرکز کاملاً جدا نگهداری می‌شوند." />
    <section className="card"><h2 className="card-title">افزودن مرکز دوم</h2><form className="form-grid form-grid--3" onSubmit={create}><label>نام مدرسه یا آموزشگاه<input value={name} required minLength={2} onChange={(e) => setName(e.target.value)} placeholder="مثلاً آموزشگاه شعبه دوم" /></label><div className="form-actions"><button className="button button--primary" disabled={busy || data.data.institutes.length >= 2}>{data.data.institutes.length >= 2 ? "سقف دو مرکز تکمیل است" : "افزودن مرکز"}</button></div></form>{error && <p className="alert alert--error">{error}</p>}</section>
    <section className="card"><h2 className="card-title">مراکز و مسئول ثبت‌نام</h2><div className="table-wrap"><table><thead><tr><th>مرکز</th><th>منشی اختصاص‌یافته</th><th>عملیات</th></tr></thead><tbody>{data.data.institutes.map((school) => <tr key={school.id}><td><strong>{school.name}</strong></td><td>{school.secretary_name ?? "هنوز منشی اختصاص داده نشده است"}</td><td><div className="button-row"><button className="button button--secondary" disabled={busy} onClick={() => void activate(school.id)}>ورود به داده‌های این مرکز</button><button className="button button--secondary" disabled={busy} onClick={() => setSecretaryFor(school.id)}>ساخت حساب منشی</button></div></td></tr>)}</tbody></table></div>
      {secretaryFor && <form className="form" onSubmit={createSecretary}><h3>ساخت حساب منشی مرکز</h3><div className="form-grid form-grid--2"><label>نام<input required value={secretary.first_name} onChange={(e) => setSecretary({ ...secretary, first_name: e.target.value })} /></label><label>نام خانوادگی<input required value={secretary.last_name} onChange={(e) => setSecretary({ ...secretary, last_name: e.target.value })} /></label><label>ایمیل ورود<input type="email" required value={secretary.email} onChange={(e) => setSecretary({ ...secretary, email: e.target.value })} /></label><label>رمز عبور اولیه<input type="password" minLength={12} required value={secretary.password} onChange={(e) => setSecretary({ ...secretary, password: e.target.value })} /></label></div><div className="button-row"><button className="button button--primary" disabled={busy}>ساخت حساب</button><button type="button" className="button button--secondary" onClick={() => setSecretaryFor(null)}>انصراف</button></div></form>}</section>
    <section className="card"><h2 className="card-title">مقایسه مالی مراکز</h2><div className="table-wrap"><table><thead><tr><th>مرکز</th><th>دانش‌آموز</th><th>شهریه ثبت‌شده</th><th>دریافتی</th><th>مانده شهریه</th><th>سررسید پیگیری</th><th>هزینه‌ها</th><th>خالص نقدی</th></tr></thead><tbody>{data.data.comparison.map((row) => <tr key={row.school_institute_id}><td><strong>{row.school_name}</strong></td><td>{row.student_count}</td><td><Money value={row.registered_tuition} /></td><td><Money value={row.received_tuition} /></td><td><Money value={row.outstanding_tuition} /></td><td><Money value={row.due_payments} /></td><td><Money value={row.costs} /></td><td><Money value={row.net_cash} /></td></tr>)}</tbody></table></div></section>
  </>;
}
