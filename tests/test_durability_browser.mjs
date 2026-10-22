/**
 * Real modal/API acceptance against tests/durability_ui_fixture.py's isolated
 * sidecar. No fetched API response or durability UI module is mocked.
 * The fixture requires A0_DURABILITY_UI_FIXTURE=isolated inside its sidecar.
 * Usage: PLAYWRIGHT_MODULE=<module-path> CHROME_EXECUTABLE=<browser-path>
 *   node tests/test_durability_browser.mjs http://127.0.0.1:<port> <output>
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE || "playwright";
const { chromium } = require(playwrightPath);
const base = new URL(process.argv[2] || "http://127.0.0.1:0");
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(base.hostname), "Use only an isolated loopback fixture URL");
assert.notEqual(base.port, "0", "Pass the sidecar's discovered published port");
const output = path.resolve(process.argv[3] || "tmp/durability-browser");
await mkdir(output, { recursive: true });
await rm(path.join(output, "failure.json"), { force: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROME_EXECUTABLE,
  headless: true,
});
const checks = [];
const errors = [];
const requests = [];
const contexts = [];

function track(page, label) {
  page.setDefaultTimeout(60_000);
  page.on("pageerror", error => errors.push(`${label}: ${error.message}`));
  page.on("requestfailed", request => errors.push(`${label}: ${request.url()} ${request.failure()?.errorText}`));
  page.on("console", message => {
    if (message.type() !== "error") return;
    // Chrome logs expected 409 business conflicts as resource errors. They are
    // independently asserted below; application exceptions remain failures.
    if (/Failed to load resource.*(?:409|403)/.test(message.text())) return;
    errors.push(`${label}: ${message.text()}`);
  });
  page.on("response", response => {
    if (response.url().startsWith(base.origin)) requests.push({ url: new URL(response.url()).pathname, status: response.status() });
  });
}

async function open(page) {
  await page.locator("#open-durability").click();
  await page.locator(".modal.show .durability-panel").waitFor();
  await page.waitForFunction(() => window.Alpine?.store("durabilityStore")?.loading === false && window.Alpine.store("durabilityStore").available);
}

async function control(page, action) {
  return page.evaluate(async action => {
    const { getCsrfToken } = await import("/js/api.js");
    const response = await fetch("/fixture/control", { method: "POST", credentials: "same-origin", headers: {
      "Content-Type": "application/json", "X-CSRF-Token": await getCsrfToken(),
    }, body: JSON.stringify({ action }) });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, action);
}

async function api(page, payload) {
  return page.evaluate(async payload => {
    const { callJsonApi } = await import("/js/api.js");
    return callJsonApi("/durability", payload);
  }, payload);
}

async function audit(page) {
  return page.evaluate(async () => (await fetch("/fixture/audit", { credentials: "same-origin" })).json());
}

function card(page, name) {
  return page.locator(".durability-card").filter({ has: page.getByRole("heading", { name, exact: true }) });
}

try {
  const anonymous = await browser.newContext();
  contexts.push(anonymous);
  const unauthorized = await anonymous.request.post(new URL("/api/durability", base).href, { data: { action: "status" }, maxRedirects: 0 });
  assert.equal(unauthorized.status(), 302, "Real auth decorator must reject a missing authenticated session");
  checks.push("unauthenticated API request rejected");

  const desktop = await browser.newContext({ viewport: { width: 1280, height: 1000 }, reducedMotion: "reduce" });
  contexts.push(desktop);
  const page = await desktop.newPage();
  track(page, "desktop");
  await page.goto(new URL("/fixture/login", base).href);
  await page.waitForFunction(() => typeof window.openModal === "function");
  const missingCsrf = await desktop.request.post(new URL("/api/durability", base).href, { data: { action: "status" } });
  assert.equal(missingCsrf.status(), 403, "Real CSRF decorator must reject an authenticated request without a token");
  checks.push("authenticated request without CSRF rejected");

  await control(page, "seed_terminal_rows");
  await open(page);
  await card(page, "Uncertain action A").waitFor();
  assert.equal(await page.locator(".durability-card").count(), 50);
  const firstTwo = await page.locator(".durability-card h3").evaluateAll(elements => elements.slice(0, 2).map(element => element.textContent));
  assert.deepEqual(new Set(firstTwo), new Set(["Uncertain action A", "Uncertain action B"]), "Older held runs must precede newer terminal rows");
  await card(page, "Uncertain action A").getByRole("checkbox").check();
  await page.getByRole("button", { name: "Load more recorded runs", exact: true }).click();
  await page.waitForFunction(() => window.Alpine.store("durabilityStore").runs.length === 57 && !window.Alpine.store("durabilityStore").loading);
  assert.equal(await page.locator(".durability-card").count(), 57);
  assert.ok(await card(page, "Uncertain action A").getByRole("checkbox").isChecked());
  assert.equal(await card(page, "Uncertain action B").getByRole("checkbox").isChecked(), false);
  await page.getByRole("button", { name: "Refresh recovery status", exact: true }).click();
  await page.waitForFunction(() => !window.Alpine.store("durabilityStore").loading && window.Alpine.store("durabilityStore").runs.length === 57);
  assert.ok(await card(page, "Uncertain action A").getByRole("checkbox").isChecked());
  assert.equal(await card(page, "Uncertain action B").getByRole("checkbox").isChecked(), false);
  assert.equal(await page.getByRole("button", { name: "Load more recorded runs", exact: true }).isVisible(), false);
  checks.push("held runs stay first, explicit pagination reaches all 57 rows, and refresh preserves only selected A");
  await page.screenshot({ path: path.join(output, "desktop-recovery.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await page.locator(".modal.show").waitFor({ state: "detached" });
  await open(page);
  checks.push("actual modal opens, closes with Escape, and reopens");

  await page.getByRole("tab", { name: "Chat plan", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#durability-plan-panel select")?.value === "ui-chat-a", null, { timeout: 10_000 });
  assert.equal(await page.locator("#durability-plan-panel select").inputValue(), "ui-chat-a", "The document chat selector must display the loaded context");
  await page.getByLabel("Plan title", { exact: true }).fill("My unsaved draft");
  await page.getByLabel("Plan item 1", { exact: true }).fill("My unsaved item");
  await control(page, "document_race");
  const conflictResponse = page.waitForResponse(response => new URL(response.url()).pathname === "/api/durability" && response.status() === 409);
  await page.getByRole("button", { name: "Save plan", exact: true }).click();
  await conflictResponse;
  await page.getByText("The saved version changed. Your draft is preserved.", { exact: true }).waitFor();
  assert.equal(await page.getByLabel("Plan title", { exact: true }).inputValue(), "My unsaved draft");
  assert.equal(await page.getByLabel("Plan item 1", { exact: true }).inputValue(), "My unsaved item");
  assert.ok(await page.getByRole("button", { name: "Save plan", exact: true }).isDisabled());
  await page.screenshot({ path: path.join(output, "desktop-document-conflict.png"), fullPage: true });
  checks.push("real document revision conflict preserves the complete dirty draft");

  await page.getByRole("tab", { name: "Recovery", exact: true }).click();
  const a = card(page, "Uncertain action A");
  await a.getByRole("button", { name: "Confirm completed", exact: true }).click();
  let review = page.getByRole("region", { name: "Review recovery decision", exact: true });
  await review.getByLabel("Evidence or note").fill("Synthetic stale review evidence");
  await review.getByLabel("I reviewed this decision and its consequences.", { exact: true }).check();
  await control(page, "bump_a");
  const staleResponse = page.waitForResponse(response => new URL(response.url()).pathname === "/api/durability" && response.status() === 409);
  await review.getByRole("button", { name: "Confirm decision", exact: true }).click();
  await staleResponse;
  await review.getByText("This run changed after submission. Retry the decision acknowledgment to check the original request.", { exact: true }).waitFor();
  const retryStaleResponse = page.waitForResponse(response => new URL(response.url()).pathname === "/api/durability" && response.status() === 409);
  await page.getByRole("button", { name: "Retry decision acknowledgment", exact: true }).click();
  await retryStaleResponse;
  await page.waitForFunction(() => !window.Alpine.store("durabilityStore").busy);
  const afterStale = await audit(page);
  assert.equal(afterStale.runs.a.status, "attention");
  assert.deepEqual(afterStale.counters, { provider_calls: 0, tool_calls: 0 });
  await review.getByRole("button", { name: "Cancel", exact: true }).click();
  checks.push("stale review rejected with no provider or tool effects");

  await a.getByRole("checkbox", { name: "Select restored run Uncertain action A", exact: true }).check();
  await page.getByRole("button", { name: "Review selected runs", exact: true }).click();
  review = page.getByRole("region", { name: "Review recovery decision", exact: true });
  await review.getByLabel("I reviewed this decision and its consequences.", { exact: true }).check();
  await review.getByRole("button", { name: "Confirm decision", exact: true }).click();
  await page.waitForFunction(() => !window.Alpine.store("durabilityStore").busy);
  const selected = await api(page, { action: "status" });
  const selectedA = selected.runs.find(run => run.context_id === "ui-chat-a");
  const selectedB = selected.runs.find(run => run.context_id === "ui-chat-b");
  assert.equal(selectedA.restore_selected, true);
  assert.equal(!!selectedB.restore_selected, false);
  assert.equal(selectedB.status, "attention");
  checks.push("selecting backup run A leaves run B held and unselected");

  await a.getByRole("button", { name: "Confirm completed", exact: true }).click();
  review = page.getByRole("region", { name: "Review recovery decision", exact: true });
  await review.getByLabel("I reviewed this decision and its consequences.", { exact: true }).check();
  assert.ok(await review.getByRole("button", { name: "Confirm decision", exact: true }).isDisabled());
  await review.getByLabel("Evidence or note").fill("Synthetic verification: the previous action was inspected; record evidence and stop.");
  await review.getByRole("button", { name: "Confirm decision", exact: true }).click();
  await page.waitForFunction(() => !window.Alpine.store("durabilityStore").busy);
  const confirmed = await audit(page);
  assert.equal(confirmed.runs.a.status, "cancelled");
  assert.equal(confirmed.runs.a.calls.find(call => call.call_id === "tool:0:0").status, "intent");
  assert.deepEqual(confirmed.counters, { provider_calls: 0, tool_calls: 0 });
  checks.push("confirmation requires evidence, stops the run, and invents no body outcome");

  await control(page, "disable");
  await page.getByRole("button", { name: "Refresh recovery status", exact: true }).click();
  await page.getByText("Recovery is disabled. Recorded work remains held; review decisions are subject to server checks.", { exact: true }).waitFor();
  for (const button of await page.getByRole("button", { name: "New attempt", exact: true }).all()) {
    if (await button.isVisible()) assert.ok(await button.isDisabled(), "Unavailable retries must not remain actionable");
  }
  checks.push("disabled recovery exposes held state without an actionable retry");

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 2, reducedMotion: "reduce" });
  contexts.push(mobile);
  const mobilePage = await mobile.newPage();
  track(mobilePage, "mobile");
  await mobilePage.goto(new URL("/fixture/login", base).href);
  await mobilePage.waitForFunction(() => typeof window.openModal === "function");
  await open(mobilePage);
  const overflow = await mobilePage.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth,
    panel: document.querySelector(".modal-inner").getBoundingClientRect().toJSON() }));
  assert.ok(overflow.page <= overflow.viewport + 1, "Mobile page must not overflow horizontally");
  assert.ok(overflow.panel.left >= 0 && overflow.panel.right <= overflow.viewport + 1, "Mobile modal must fit the viewport");
  await mobilePage.screenshot({ path: path.join(output, "mobile-recovery.png"), fullPage: true });
  await mobilePage.locator(".modal-close").click();
  await mobilePage.locator(".modal.show").waitFor({ state: "detached" });
  checks.push("mobile modal fits the viewport and closes through its real control");

  assert.deepEqual(errors, [], "No unexpected browser errors or failed requests");
  const finalAudit = await audit(page);
  const receipt = { status: "passed", checks, counters: finalAudit.counters, source_hashes: finalAudit.source_hashes, errors, requests,
    screenshots: ["desktop-recovery.png", "desktop-document-conflict.png", "mobile-recovery.png"].map(name => path.join(output, name)) };
  await writeFile(path.join(output, "receipt.json"), JSON.stringify(receipt, null, 2) + "\n");
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  for (const [index, context] of contexts.entries()) for (const [pageIndex, page] of context.pages().entries()) {
    if (!page.isClosed()) await page.screenshot({ path: path.join(output, `failure-${index}-${pageIndex}.png`), fullPage: true }).catch(() => {});
  }
  await writeFile(path.join(output, "failure.json"), JSON.stringify({ error: error.stack, checks, errors, requests }, null, 2) + "\n");
  throw error;
} finally {
  await Promise.all(contexts.map(context => context.close()));
  await browser.close();
}
