import { useState, type FormEvent } from "react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import { DateField, DateText, ErrorState, Field, Modal } from "./ui";
import { toGregorian } from "../utils/jalaali";

export interface AcademicYear { id: string; name: string; starts_on: string; ends_on: string }
export const INITIAL_ACADEMIC_YEAR = "1405/1406";
export function academicYearDates(name: string) {
  const first = Number(name.split("/")[0]);
  if (!/^1\d{3}\/1\d{3}$/.test(name)) return { starts_on: "", ends_on: "" };
  const iso = (jy: number, jm: number, jd: number) => {
    const d = toGregorian(jy, jm, jd);
    return `${d.gy}-${String(d.gm).padStart(2, "0")}-${String(d.gd).padStart(2, "0")}`;
  };
  return { starts_on: iso(first, 7, 1), ends_on: iso(first + 1, 3, 31) };
}

export function AcademicYearField({ value, onChange, disabled = false, manage = false }: {
  value: string; onChange: (value: string) => void; disabled?: boolean; manage?: boolean;
}) {
  const years = useAsync(() => api.get<AcademicYear[]>("/school/academic-years"), []);
  const [editing, setEditing] = useState<AcademicYear | "new" | null>(null);
  const selected = years.data?.find((row) => row.name === value);
  return <section>
    <Field label="سال تحصیلی"><select required value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled || years.loading}>
      <option value="">انتخاب سال تحصیلی</option>
      {years.data?.map((row) => <option key={row.id} value={row.name}>{row.name}</option>)}
    </select></Field>
    {years.error && <ErrorState message={years.error} retry={years.reload} />}
    {selected && <p className="muted">از <DateText value={selected.starts_on} /> تا <DateText value={selected.ends_on} /></p>}
    {manage && <div className="button-row"><button type="button" className="button button--secondary button--small" onClick={() => setEditing("new")}>سال تحصیلی جدید</button><button type="button" className="button button--secondary button--small" disabled={!selected} onClick={() => selected && setEditing(selected)}>ویرایش تاریخ‌های سال</button></div>}
    {editing && <AcademicYearForm year={editing === "new" ? undefined : editing} close={() => setEditing(null)} saved={(name) => { setEditing(null); onChange(name); void years.reload(); }} />}
  </section>;
}

function AcademicYearForm({ year, close, saved }: { year?: AcademicYear; close: () => void; saved: (name: string) => void }) {
  const [name, setName] = useState(year?.name ?? "1406/1407");
  const defaults = academicYearDates(name);
  const [start, setStart] = useState(year?.starts_on ?? defaults.starts_on);
  const [end, setEnd] = useState(year?.ends_on ?? defaults.ends_on);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const body = { name, starts_on: start, ends_on: end };
      if (year) await api.patch("/school/academic-years", body);
      else await api.post("/school/academic-years", body);
      saved(name);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "ثبت سال ناموفق بود."); }
    finally { setBusy(false); }
  }
  return <Modal open title={year ? "ویرایش تاریخ‌های سال تحصیلی" : "سال تحصیلی جدید"} onClose={close}><form className="form" onSubmit={submit}>
    {error && <p role="alert" className="alert alert--error">{error}</p>}
    <Field label="سال تحصیلی (مثلاً 1406/1407)"><input dir="ltr" value={name} readOnly={!!year} required pattern="1[0-9]{3}/1[0-9]{3}" onChange={(e) => { setName(e.target.value); const dates = academicYearDates(e.target.value); setStart(dates.starts_on); setEnd(dates.ends_on); }} /></Field>
    <DateField label="شروع سال تحصیلی" value={start} onChange={setStart} required />
    <DateField label="پایان سال تحصیلی" value={end} onChange={setEnd} required />
    <p className="muted">تاریخ‌ها قابل تغییرند. پیش‌ثبت‌نام قبل از شروع سال مجاز است. قیمت‌ها و پرونده‌های قبلی تغییر نمی‌کنند.</p>
    <div className="form-actions"><button type="button" className="button button--secondary" onClick={close} disabled={busy}>انصراف</button><button className="button button--primary" disabled={busy || !start || !end}>ذخیره</button></div>
  </form></Modal>;
}
