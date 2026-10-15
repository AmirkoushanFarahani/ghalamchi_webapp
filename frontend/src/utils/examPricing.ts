import type { ExamPricingPeriod } from "../types/api";
import { formatDate } from "./date";

export function examPeriodLabel(period: ExamPricingPeriod) {
  return `${period.name} (${period.starts_on ? formatDate(period.starts_on) : "از ابتدا"} تا ${period.ends_on ? formatDate(period.ends_on) : "بدون پایان"})`;
}

export function currentExamPeriod(periods: ExamPricingPeriod[], on: string) {
  return periods.filter((period) => (!period.starts_on || period.starts_on <= on) && (!period.ends_on || period.ends_on >= on))
    .sort((a, b) => (b.starts_on ?? "").localeCompare(a.starts_on ?? ""))[0];
}
