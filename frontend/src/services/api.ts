import type { ApiErrorBody, RegisterRequest, TokenResponse, User } from "../types/api";
export const API_URL = import.meta.env.VITE_API_URL ?? "/api/v1";
const messages: Record<number, string> = { 400: "اطلاعات درخواست نامعتبر است.", 401: "نشست شما پایان یافته است. لطفاً دوباره وارد شوید.", 403: "شما اجازه انجام این عملیات را ندارید.", 404: "اطلاعات درخواستی پیدا نشد.", 409: "این عملیات با وضعیت فعلی اطلاعات سازگار نیست.", 422: "لطفاً اطلاعات واردشده را بررسی کنید.", 500: "خطایی در سرور رخ داده است. کمی بعد دوباره تلاش کنید.", 503: "سرویس موردنظر اکنون در دسترس نیست." };
const fieldLabels: Record<string, string> = {
  full_name: "نام دانش‌آموز", national_id: "کد ملی", birth_date: "تاریخ تولد", grade: "پایه تحصیلی",
  academic_track: "رشته تحصیلی", guardian_full_name: "نام ولی", guardian_phone: "تلفن ولی",
  course_ids: "کلاس‌ها", exam_plan_id: "طرح آزمون", payments: "پرداخت‌ها", due_date: "تاریخ سررسید",
  amount: "مبلغ", method: "روش پرداخت", registration_date: "تاریخ ثبت‌نام",
};
const exactDetails: Record<string, string> = {
  "One or more selected courses are unavailable": "یک یا چند کلاس انتخاب‌شده دیگر فعال یا در دسترس نیستند.",
  "Every selected course must match the student's grade": "همه کلاس‌های انتخاب‌شده باید با پایه تحصیلی دانش‌آموز یکسان باشند.",
  "Immediate payments cannot exceed the enrollment total": "جمع پرداخت‌های نقدی یا انتقال بانکی نمی‌تواند بیشتر از مبلغ نهایی فاکتور باشد.",
  "A student with this national ID already exists": "دانش‌آموزی با این کد ملی در همین آموزشگاه قبلاً ثبت شده است.",
  "Select an exam plan before adding exams or books": "برای ثبت آزمون یا بن کتاب، ابتدا طرح آزمون مناسب را انتخاب کنید.",
  "The selected exam plan is unavailable": "طرح آزمون انتخاب‌شده فعال یا در دسترس نیست.",
  "The selected exam plan does not match this student's grade and major": "طرح آزمون با پایه یا رشته تحصیلی دانش‌آموز مطابقت ندارد.",
  "The discount code is invalid or inactive": "کد تخفیف معتبر نیست یا غیرفعال شده است.",
  "The discount code has expired": "تاریخ اعتبار کد تخفیف تمام شده است.",
  "The discount code has reached its use limit": "تعداد مجاز استفاده از این کد تخفیف تمام شده است.",
};
export class ApiError extends Error { constructor(public readonly status: number, message: string, public readonly body?: ApiErrorBody) { super(message); this.name = "ApiError"; } }
let tokenProvider: () => string | null = () => sessionStorage.getItem("azari_token");
let unauthorizedHandler: (() => void) | undefined;
export function configureApi(getToken: () => string | null, onUnauthorized: () => void) { tokenProvider = getToken; unauthorizedHandler = onUnauthorized; }
function validationDetail(body?: ApiErrorBody) {
  if (!body?.detail) return null;
  if (typeof body.detail === "string") return exactDetails[body.detail] ?? body.detail;
  const details = body.detail.map((item) => {
    const field = item.loc?.filter((part) => part !== "body").at(-1);
    const label = typeof field === "string" ? fieldLabels[field] ?? field : "اطلاعات فرم";
    const message = item.msg === "Field required" ? "الزامی است" : item.msg ?? "نامعتبر است";
    return `${label}: ${message}`;
  }).filter(Boolean);
  return details.length ? `لطفاً این موارد را اصلاح کنید: ${details.join("، ")}` : null;
}
function friendlyMessage(status: number, body?: ApiErrorBody) {
  return validationDetail(body) ?? messages[status] ?? "ارتباط با سرور ناموفق بود.";
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers); if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = tokenProvider(); if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response; try { response = await fetch(`${API_URL}${path}`, { ...options, headers }); } catch { throw new ApiError(0, "ارتباط با سرور برقرار نشد. اتصال شبکه را بررسی کنید."); }
  const body = response.status === 204 ? undefined : await response.json().catch(() => undefined) as ApiErrorBody | undefined;
  if (!response.ok) { if (response.status === 401) unauthorizedHandler?.(); throw new ApiError(response.status, friendlyMessage(response.status, body), body); }
  return body as T;
}
export function query(path: string, params: Record<string, string | undefined | null>) { const search = new URLSearchParams(); Object.entries(params).forEach(([key, value]) => { if (value) search.set(key, value); }); return `${path}${search.size ? `?${search}` : ""}`; }
export const api = { get: <T>(path: string) => request<T>(path), post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }), put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }), patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }), register: (data: RegisterRequest) => request<User>("/auth/register", { method: "POST", body: JSON.stringify(data), headers: { "Content-Type": "application/json" } }), login: (identifier: string, password: string) => request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(identifier.startsWith("+") ? { phone_number: identifier, password } : { email: identifier, password }), headers: { "Content-Type": "application/json" } }), me: () => request<User>("/auth/me") };
export interface HealthResponse { status: "ok"; service: string; timestamp: string }
export const getHealth = (signal?: AbortSignal) => request<HealthResponse>("/health", { signal });
