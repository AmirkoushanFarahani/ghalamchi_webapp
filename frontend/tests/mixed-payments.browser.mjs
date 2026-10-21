// Real shared form; synthetic preview responses. Exact calendar/math also tested in Python.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { build } from "vite";
const require = createRequire(process.env.PLAYWRIGHT_PACKAGE_JSON || "playwright/package.json");
const { chromium } = require("playwright");
await build({ build: { outDir: ".test-dist/mixed", emptyOutDir: true, rollupOptions: { input: "tests/mixed-payments.fixture.tsx", output: { entryFileNames: "fixture.js" } } } });
const script = await readFile(".test-dist/mixed/fixture.js");
const server = createServer((req, res) => {
  res.writeHead(200, { "Content-Type": req.url === "/fixture.js" ? "application/javascript" : "text/html; charset=utf-8" });
  res.end(req.url === "/fixture.js" ? script : '<html lang="fa" dir="rtl"><div id="root"></div><script type="module" src="/fixture.js"></script></html>');
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage();
  const errors = []; page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/school/payment-plan/preview", async (route) => {
    const { plan, total } = route.request().postDataJSON();
    const assigned = plan.items.reduce((sum, item) => sum + Number(item.amount), 0);
    const invalid = plan.items.some((item) => Number(item.amount) <= 0 || (item.method === "CHECK" && !item.due_date)) || assigned > Number(total) || (assigned < Number(total) && !plan.installment_count);
    if (invalid) return route.fulfill({ status: 422, json: { detail: "برنامه پرداخت باید کل فاکتور را پوشش دهد." } });
    const items = [...plan.items];
    const cents = Math.round((Number(total) - assigned) * 100);
    for (let i = 0; i < plan.installment_count; i++) items.push({ method: plan.installment_method ?? "INSTALLMENT", amount: String((Math.floor(cents / plan.installment_count) + (i < cents % plan.installment_count ? 1 : 0)) / 100), due_date: ["2026-10-22", "2026-11-21", "2026-12-21"][i] });
    const immediate = plan.items.filter((item) => item.method !== "CHECK").reduce((sum, item) => sum + Number(item.amount), 0);
    await route.fulfill({ json: { total, immediate: String(immediate), scheduled: String(Number(total) - immediate), items } });
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const save = page.getByRole("button", { name: "Save synthetic plan" });
  assert.equal(await page.getByLabel("نحوه پرداخت", { exact: true }).locator("option").count(), 3);
  await save.click();
  assert.equal(JSON.parse(await page.locator("body").getAttribute("data-saved")).installment_count, 0);
  await page.getByLabel("نحوه پرداخت", { exact: true }).selectOption("INSTALLMENTS");
  await page.locator("tbody tr").filter({ hasText: "قسط" }).first().waitFor();
  assert.equal(await page.locator("tbody tr").count(), 3);
  await save.click();
  let stored = JSON.parse(await page.locator("body").getAttribute("data-saved"));
  assert.equal(stored.items.length, 0);
  assert.equal(stored.installment_count, 3);
  await page.getByLabel("نحوه پرداخت", { exact: true }).selectOption("ADVANCE");
  await page.getByRole("alert").waitFor();
  assert.equal(await save.isDisabled(), true);
  await page.getByLabel("مبلغ پیش‌پرداخت", { exact: true }).fill("300");
  await page.locator("tbody tr").filter({ hasText: "قسط" }).first().waitFor();
  assert.equal(await page.locator("tbody tr").count(), 4);
  await page.getByLabel("نحوه پرداخت اقساط", { exact: true }).selectOption("CHECK");
  await page.locator("tbody tr").filter({ hasText: "چک" }).first().waitFor();
  // Every identifying field is optional; server supplies each missing due date.
  await save.click();
  stored = JSON.parse(await page.locator("body").getAttribute("data-saved"));
  assert.equal(stored.installment_method, "CHECK");
  assert.equal(stored.installment_count, 3);
  assert.deepEqual(stored.check_details, []);
  assert.equal(stored.items.length, 1);
  assert.equal(stored.items[0].amount, "300");
  await page.getByText("اطلاعات اختیاری چک 1", { exact: true }).click();
  await page.getByLabel("شناسه صیادی چک 1", { exact: true }).fill("123456789");
  await save.click();
  stored = JSON.parse(await page.locator("body").getAttribute("data-saved"));
  assert.equal(stored.check_details[0].sayad_id, "123456789");
  assert.deepEqual(errors, []);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.getByLabel("مبلغ پیش‌پرداخت", { exact: true }).isVisible(), true);
  console.log("PASS three payment choices, automatic installments, upfront validation, optional check details and mobile inputs");
} finally { await browser?.close(); await new Promise((resolve) => server.close(resolve)); }
