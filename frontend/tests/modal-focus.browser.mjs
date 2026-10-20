// Run from frontend. Supply PLAYWRIGHT_PACKAGE_JSON when using the bundled runtime.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { build } from "vite";

const require = createRequire(process.env.PLAYWRIGHT_PACKAGE_JSON ?? import.meta.url);
const { chromium } = require("playwright");
await build({ build: {
  outDir: ".test-dist/modal-focus", emptyOutDir: true,
  rollupOptions: { input: "tests/modal-focus.fixture.tsx", output: { entryFileNames: "fixture.js" } },
} });
const script = await readFile(".test-dist/modal-focus/fixture.js");
const server = createServer((request, response) => {
  if (request.url === "/fixture.js") {
    response.writeHead(200, { "Content-Type": "application/javascript" }); response.end(script);
  } else if (request.url === "/") {
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end('<!doctype html><html lang="fa" dir="rtl"><div id="root"></div><script type="module" src="/fixture.js"></script></html>');
  } else { response.writeHead(404); response.end(); }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: "chrome" });
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const opener = page.locator("#opener");
  await opener.click();
  const reason = page.locator("#reason");
  await reason.click();
  const sentence = "دانش‌آموز درخواست تغییر کلاس و دبیر را دارد";
  await reason.pressSequentially(sentence, { delay: 5 });
  assert.equal(await reason.inputValue(), sentence);
  assert.ok(await reason.evaluate((element) => element === document.activeElement));
  await reason.press("Enter");
  await reason.pressSequentially("به دلیل تغییر برنامه هفتگی", { delay: 5 });
  assert.equal(await reason.inputValue(), sentence + "\nبه دلیل تغییر برنامه هفتگی");
  // Updating the close guard must not re-focus, and Escape must use the latest guard.
  const guard = page.locator("#busy");
  await guard.click();
  await reason.click();
  await reason.press("Escape");
  assert.equal(await page.getByRole("dialog").count(), 1);
  await guard.click();
  await guard.press("Tab");
  assert.ok(await page.getByRole("button", { name: "بستن", exact: true }).evaluate((e) => e === document.activeElement));
  await page.keyboard.press("Shift+Tab");
  assert.ok(await guard.evaluate((e) => e === document.activeElement));
  await reason.fill("");
  await reason.pressSequentially("س".repeat(501));
  assert.equal((await reason.inputValue()).length, 500);
  await reason.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  assert.ok(await opener.evaluate((e) => e === document.activeElement));
  console.log("PASS: sentences/newlines/500-character limit, stable typing focus, latest close guard, Tab trap and focus restoration");
} finally {
  await browser?.close();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
