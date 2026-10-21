import { useState, type FormEvent } from "react";
import { DateField, Field, Modal } from "../components/ui";
import { api } from "../services/api";
import type { Student, SchoolGrade } from "../types/api";

export function StudentEditModal({ student, close, saved }: { student: Student; close: () => void; saved: () => void }) {
  const [grade, setGrade] = useState<SchoolGrade>(student.grade);
  const [birth, setBirth] = useState(student.birth_date);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    const fields = ["full_name", "national_id", "student_phone", "guardian_full_name", "guardian_phone", "mother_full_name", "mother_phone", "address", "previous_school", "emergency_contact", "notes"];
    const data = Object.fromEntries(fields.map((name) => [name, String(form.get(name) ?? "").trim() || null]));
    try { await api.patch(`/school/students/${student.id}`, { ...data, birth_date: birth, grade, academic_track: Number(grade.replace("GRADE_", "")) >= 10 ? form.get("academic_track") || null : null }); saved(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "ویرایش اطلاعات ناموفق بود."); } finally { setBusy(false); }
  }
  return <Modal open wide title="ویرایش اطلاعات دانش‌آموز" onClose={() => { if (!busy) close(); }}><form className="form" onSubmit={submit}>
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    <p className="form-description">این بخش مشخصات و پایه فعلی دانش‌آموز را ویرایش می‌کند. سال تحصیلی، پایه ثبت‌نام‌های قبلی، کلاس‌های خریداری‌شده و مبالغ فاکتور تغییر نمی‌کنند.</p>
    <div className="form-grid form-grid--2">
      <Field label="نام و نام خانوادگی دانش‌آموز"><input name="full_name" defaultValue={student.full_name} required minLength={3} maxLength={200} disabled={busy} /></Field>
      <Field label="کد ملی"><input name="national_id" defaultValue={student.national_id} required minLength={5} maxLength={20} dir="ltr" disabled={busy} /></Field>
      <DateField label="تاریخ تولد" value={birth} onChange={setBirth} required />
      <Field label="پایه فعلی دانش‌آموز"><select aria-label="پایه فعلی دانش‌آموز" value={grade} onChange={(e) => setGrade(e.target.value as SchoolGrade)} disabled={busy}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={`GRADE_${i + 1}`}>پایه {i + 1}</option>)}</select></Field>
      {Number(grade.replace("GRADE_", "")) >= 10 && <Field label="رشته تحصیلی"><input name="academic_track" defaultValue={student.academic_track ?? ""} maxLength={100} disabled={busy} /></Field>}
      <Field label="تلفن دانش‌آموز (اختیاری)"><input name="student_phone" defaultValue={student.student_phone ?? ""} maxLength={32} dir="ltr" disabled={busy} /></Field>
      <Field label="نام و نام خانوادگی پدر"><input name="guardian_full_name" defaultValue={student.guardian_full_name} required minLength={3} maxLength={200} disabled={busy} /></Field>
      <Field label="تلفن پدر"><input name="guardian_phone" defaultValue={student.guardian_phone} required minLength={7} maxLength={32} dir="ltr" disabled={busy} /></Field>
      <Field label="نام و نام خانوادگی مادر (اختیاری)"><input name="mother_full_name" defaultValue={student.mother_full_name ?? ""} maxLength={200} disabled={busy} /></Field>
      <Field label="شماره تماس مادر (اختیاری)"><input name="mother_phone" defaultValue={student.mother_phone ?? ""} maxLength={32} dir="ltr" disabled={busy} /></Field>
      <Field label="مدرسه قبلی (اختیاری)"><input name="previous_school" defaultValue={student.previous_school ?? ""} maxLength={200} disabled={busy} /></Field>
      <Field label="تماس اضطراری (اختیاری)"><input name="emergency_contact" defaultValue={student.emergency_contact ?? ""} maxLength={200} disabled={busy} /></Field>
    </div>
    <Field label="نشانی (اختیاری)"><textarea name="address" defaultValue={student.address ?? ""} maxLength={500} disabled={busy} /></Field>
    <Field label="یادداشت (اختیاری)"><textarea name="notes" defaultValue={student.notes ?? ""} maxLength={1000} disabled={busy} /></Field>
    <div className="form-actions"><button type="button" className="button button--secondary" disabled={busy} onClick={close}>انصراف</button><button className="button button--primary" disabled={busy}>{busy ? "در حال ذخیره…" : "ذخیره اطلاعات دانش‌آموز"}</button></div>
  </form></Modal>;
}
