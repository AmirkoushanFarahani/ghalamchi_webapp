import type { ExamPricingPeriod } from "../types/api";
import { examPeriodLabel, orderedExamPeriods } from "../utils/examPricing";
import { Field } from "./ui";

export function ExamPeriodSelect({ periods, value, onChange, disabled = false }: {
  periods: ExamPricingPeriod[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return <Field label="بازه قیمت آزمون">
    <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
      <option value="current">بازه جاری براساس تاریخ امروز</option>
      <option value="all">همه بازه‌ها</option>
      <optgroup label="بازه‌های تاریخ قیمت آزمون">
        {orderedExamPeriods(periods).map((period) =>
          <option key={period.id} value={period.id}>{examPeriodLabel(period)}</option>,
        )}
      </optgroup>
      <option value="legacy">تعرفه‌های قبلی بدون تاریخ</option>
    </select>
  </Field>;
}
