import type { ExamPricingPeriod } from "../types/api";
import { formatDate } from "./date";

export function examPeriodLabel(period: ExamPricingPeriod) {
  return `${period.name} (${period.starts_on ? formatDate(period.starts_on) : "از ابتدا"} تا ${period.ends_on ? formatDate(period.ends_on) : "بدون پایان"})`;
}

export function currentExamPeriod(periods: ExamPricingPeriod[], on: string) {
  return periods.filter((period) => (!period.starts_on || period.starts_on <= on) && (!period.ends_on || period.ends_on >= on))
    .sort((a, b) => (b.starts_on ?? "").localeCompare(a.starts_on ?? ""))[0];
}

export function orderedExamPeriods(periods: ExamPricingPeriod[]) {
  return [...periods].sort((a, b) =>
    (a.starts_on ?? "").localeCompare(b.starts_on ?? "") ||
    (a.ends_on ?? "9999-12-31").localeCompare(b.ends_on ?? "9999-12-31") ||
    a.name.localeCompare(b.name, "fa"),
  );
}

export function examPeriodGroups(periods: ExamPricingPeriod[], selected: string, on: string) {
  const chosen = selected === "current" ? currentExamPeriod(periods, on)?.id : selected;
  return [
    ...orderedExamPeriods(periods).map((period) => ({ id: period.id, label: examPeriodLabel(period) })),
    { id: "legacy", label: "تعرفه‌های قبلی بدون بازه تاریخ" },
  ].filter((period) => chosen === "all" || period.id === chosen);
}
