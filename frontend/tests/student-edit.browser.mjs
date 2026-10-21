// Real edit modal with synthetic HTTP response; no student database writes.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { build } from "vite";
const require = createRequire(process.env.PLAYWRIGHT_PACKAGE_JSON || "playwright/package.json");
const { chromium } = require("playwright");
await build({ build: { outDir: ".test-dist/student-edit", emptyOutDir: true, rollupOptions: { input: "tests/student-edit.fixture.tsx", output: { entryFileNames: "fixture.js" } } } });
const script = await readFile(".test-dist/student-edit/fixture.js");
const server = createServer((req, res) => {
  res.writeHead(200, { "Content-Type": req.url === "/fixture.js" ? "application/javascript" : "text/html; charset=utf-8" });
  res.end(req.url === "/fixture.js" ? script : '<html lang="fa" dir="rtl"><div id="root"></div><script type="module" src="/fixture.js"></script></html>');
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser; let submitted;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage();
  const errors = []; page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/school/students/synthetic-only", async (route) => {
    assert.equal(route.request().method(), "PATCH");
    submitted = route.request().postDataJSON();
    await route.fulfill({ json: { id: "synthetic-only", ...submitted } });
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.getByLabel("نام و نام خانوادگی دانش‌آموز", { exact: true }).fill("نام جدید دانش‌آموز آزمایشی");
  await page.getByLabel("کد ملی", { exact: true }).fill("9876543210");
  await page.getByLabel("پایه فعلی دانش‌آموز", { exact: true }).selectOption("GRADE_8");
  await page.getByLabel("نام و نام خانوادگی پدر", { exact: true }).fill("پدر آزمایشی");
  await page.getByLabel("نام و نام خانوادگی مادر (اختیاری)", { exact: true }).fill("مادر آزمایشی");
  await page.getByLabel("شماره تماس مادر (اختیاری)", { exact: true }).fill("09120000002");
  await page.getByLabel("یادداشت (اختیاری)", { exact: true }).fill("توضیح چند کلمه‌ای\nخط دوم");
  assert.equal(await page.locator('[name="academic_year"]').count(), 0);
  await page.getByRole("button", { name: "ذخیره اطلاعات دانش‌آموز", exact: true }).click();
  await page.waitForFunction(() => document.body.dataset.saved === "true");
  assert.equal(submitted.grade, "GRADE_8");
  assert.equal(submitted.mother_full_name, "مادر آزمایشی");
  assert.equal(submitted.mother_phone, "09120000002");
  assert.equal(submitted.guardian_full_name, "پدر آزمایشی");
  assert.equal("academic_year" in submitted, false);
  assert.deepEqual(errors, []);
  console.log("PASS real student edit modal: multi-word names, grade, father/mother contact, notes, no school-year mutation");
} finally { await browser?.close(); await new Promise((resolve) => server.close(resolve)); }
