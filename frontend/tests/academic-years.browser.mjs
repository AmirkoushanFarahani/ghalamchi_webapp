// Real browser, real registration components, synthetic HTTP fixtures; no database writes.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { build } from "vite";
const require = createRequire(process.env.PLAYWRIGHT_PACKAGE_JSON || "playwright/package.json");
const { chromium } = require("playwright");
await build({ build: { outDir: ".test-dist/academic-years", emptyOutDir: true, rollupOptions: { input: "tests/academic-years.fixture.tsx", output: { entryFileNames: "fixture.js" } } } });
const script = await readFile(".test-dist/academic-years/fixture.js");
const server = createServer((req, res) => {
  res.writeHead(200, { "Content-Type": req.url === "/fixture.js" ? "application/javascript" : "text/html; charset=utf-8" });
  res.end(req.url === "/fixture.js" ? script : '<html lang="fa" dir="rtl"><div id="root"></div><script type="module" src="/fixture.js"></script></html>');
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const years = [{ id: "year1", name: "1405/1406", starts_on: "2026-09-23", ends_on: "2027-06-21" }, { id: "year2", name: "1406/1407", starts_on: "2027-09-23", ends_on: "2028-06-20" }];
const courses = [{ id: "class1", name: "کلاس امسال", grade: "GRADE_4", academic_year: "1405/1406", price: "1000000", is_active: true, session_count: 20 }, { id: "class2", name: "کلاس سال آینده", grade: "GRADE_5", academic_year: "1406/1407", price: "2000000", is_active: true, session_count: 20 }];
const periods = years.map((year, i) => ({ id: `period${i}`, name: "پاییز", academic_year: year.name, starts_on: year.starts_on, ends_on: year.ends_on }));
const plans = years.map((year, i) => ({ id: `exam${i}`, academic_year: year.name, grade: i ? "GRADE_5" : "GRADE_4", academic_track: null, plan_code: `EXAM${i}`, exam_count: 20, exam_total: "500000", book_voucher_amount: "300000", book_voucher_discount: "0", is_active: true, is_current: true, pricing_period_id: `period${i}` }));
let browser; let submitted;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage();
  const errors = []; page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/school/**", async (route) => {
    const path = new URL(route.request().url()).pathname.split("/").at(-1);
    let data = ({ "academic-years": years, courses, "exam-plans": plans, "special-supports": [], "exam-pricing-periods": periods })[path];
    if (path === "student-lookup") data = { id: "student1", full_name: "دانش‌آموز آزمایشی", birth_date: "2015-01-01", guardian_full_name: "ولی آزمایشی", guardian_phone: "09120000000", enrollments: [] };
    if (path === "enroll") { submitted = route.request().postDataJSON(); data = {}; }
    assert.notEqual(data, undefined, path);
    await route.fulfill({ json: data });
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const select = (label) => page.locator("label.field").filter({ has: page.getByText(label, { exact: true }) }).locator("select");
  const year = select("سال تحصیلی");
  await year.selectOption("1405/1406");
  await select("پایه تحصیلی").selectOption("GRADE_4");
  await page.getByText("کلاس امسال", { exact: true }).waitFor();
  assert.equal(await page.getByText("کلاس سال آینده", { exact: true }).count(), 0);
  await page.locator('input[name="national_id"]').fill("0250155710");
  await page.getByRole("button", { name: "بازیابی اطلاعات", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "اطلاعات پرونده قبلی" }).waitFor();
  assert.equal(await page.getByLabel("نام", { exact: true }).inputValue(), "دانش‌آموز");
  assert.equal(await page.getByLabel("نام ولی", { exact: true }).inputValue(), "ولی آزمایشی");
  await year.selectOption("1406/1407");
  await select("پایه تحصیلی").selectOption("GRADE_5");
  await page.getByText("کلاس سال آینده", { exact: true }).waitFor();
  assert.equal(await page.getByText("کلاس امسال", { exact: true }).count(), 0);
  await page.locator(".course-choice").filter({ hasText: "کلاس سال آینده" }).locator("input").check();
  await select("بازه قیمت آزمون و بن کتاب").selectOption("period1");
  const examSelect = select("طرح آزمون و بن کتاب");
  assert.match(await examSelect.innerText(), /EXAM1/);
  assert.doesNotMatch(await examSelect.innerText(), /EXAM0/);
  await page.getByRole("button", { name: "ثبت‌نام و صدور فاکتور" }).click();
  await page.waitForFunction(() => document.body.dataset.saved === "true");
  assert.equal(submitted.academic_year, "1406/1407");
  assert.equal(submitted.grade, "GRADE_5");
  assert.deepEqual(submitted.course_ids, ["class2"]);
  assert.equal(submitted.national_id, "0250155710");
  assert.equal(submitted.payments[0].amount, "2000000.00");
  assert.deepEqual(errors, []);
  console.log("PASS: year/grade class filtering, year-specific exams, national-ID prefill, future-year registration payload and pricing");
} finally { await browser?.close(); await new Promise((resolve) => server.close(resolve)); }
