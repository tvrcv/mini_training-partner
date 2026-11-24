// Loads the unpacked extension into Chromium and drives a mock claude.ai page.
// Run: node --test tests/extension/e2e.test.js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..", "..");
const EXT = path.join(ROOT, "extension");
const SHOTS = process.env.TS_SCREENSHOT_DIR; // set to save screenshots of the tip, toast and popup
const shot = (page, name) => (SHOTS ? page.screenshot({ path: path.join(SHOTS, name) }) : null);
const MOCK = fs.readFileSync(path.join(__dirname, "mock-claude.html"), "utf8");

async function launch() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "ts-profile-"));
  const ctx = await chromium.launchPersistentContext(profile, {
    channel: "chromium",
    headless: true,
    args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
    viewport: { width: 1100, height: 800 },
  });
  await ctx.route("https://claude.ai/**", (r) => r.fulfill({ status: 200, contentType: "text/html", body: MOCK }));
  const page = await ctx.newPage();
  await page.goto("https://claude.ai/new");
  return { ctx, page, profile };
}

const shadowText = (page, cls) => page.evaluate((c) => {
  const host = document.getElementById("token-steward-root");
  const el = host && host.shadowRoot.querySelector("." + c);
  return el && !el.hidden ? el.innerText : null;
}, cls);

async function waitFor(fn, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = await fn(); if (v) return v; await new Promise((r) => setTimeout(r, 150)); }
  return null;
}

// Chrome derives an unpacked extension's id from its path: sha256 -> first 32 hex digits -> a..p.
function extensionId() {
  const hex = require("node:crypto").createHash("sha256").update(EXT).digest("hex").slice(0, 32);
  return [...hex].map((c) => String.fromCharCode(97 + parseInt(c, 16))).join("");
}

async function readStorage(ctx) {
  const p = await ctx.newPage();
  await p.goto(`chrome-extension://${extensionId()}/popup/popup.html`);
  const data = await p.evaluate(() => new Promise((r) => chrome.storage.local.get(null, r)));
  await shot(p, "ts-popup.png");
  await p.close();
  return data;
}

async function type(page, text) {
  await page.click(".ProseMirror");
  await page.keyboard.type(text);
}

test("tip while typing, no block on send, thanks after switching", { timeout: 60000 }, async () => {
  const { ctx, page, profile } = await launch();
  try {
    await waitFor(() => page.evaluate(() => !!document.getElementById("token-steward-root")));

    // A real piece of work first: no tip.
    await type(page, "Design the system architecture for the engagement data platform");
    await page.waitForTimeout(1200);
    assert.strictEqual(await shadowText(page, "ts-tip"), null);
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2000);

    // Light request on Opus with thinking on: tip appears before sending.
    await type(page, "Rephrase this email to the client so it sounds more formal");
    const tip = await waitFor(() => shadowText(page, "ts-tip"));
    assert.ok(tip, "tip should appear");
    assert.match(tip, /quick, lightweight request/);
    assert.match(tip, /pick Haiku in the model menu/);
    await shot(page, "ts-tip.png");

    // Inline mode never blocks: Enter sends as usual.
    await page.keyboard.press("Enter");
    assert.strictEqual((await page.evaluate(() => window.sent)).length, 2);
    await page.waitForTimeout(2000);

    // The person switches to Haiku with thinking off, sends two more light requests.
    await page.evaluate(() => {
      document.getElementById("model").textContent = "Haiku 5.5";
      document.getElementById("thinking").setAttribute("aria-pressed", "false");
    });
    await type(page, "ok");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2000);
    await type(page, "Now shorten the second paragraph");
    await page.keyboard.press("Enter");
    const thanks = await waitFor(() => shadowText(page, "ts-toast"));
    assert.ok(thanks, "thank-you toast should appear");
    assert.match(thanks, /Thank/);
    assert.doesNotMatch(thanks, /about </);
    assert.match(thanks, /less than Opus 5\.5 at high effort/);
    await shot(page, "ts-thanks.png");

    // Savings were recorded, and nothing typed was stored.
    await page.waitForTimeout(2500);
    const local = await readStorage(ctx);
    assert.ok(local.totals.allTime.turns >= 4);
    assert.ok(local.totals.allTime.savings > 0);
    assert.strictEqual(local.totals.tipsAccepted, 1);
    const dump = JSON.stringify(local);
    assert.doesNotMatch(dump, /Rephrase|formal|paragraph/);
  } finally {
    await ctx.close();
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch (e) { /* best effort */ }
  }
});

test("two claude.ai tabs both count towards the same totals", { timeout: 60000 }, async () => {
  const { ctx, page, profile } = await launch();
  try {
    const page2 = await ctx.newPage();
    await page2.goto("https://claude.ai/new");
    for (const p of [page, page2]) {
      await waitFor(() => p.evaluate(() => !!document.getElementById("token-steward-root")));
      await p.evaluate(() => { document.getElementById("model").textContent = "Sonnet 5.5"; });
    }
    // Both tabs are used; a tab only sends again once its previous reply has finished, as on claude.ai.
    const replyDone = (p) => waitFor(() => p.evaluate(() =>
      !document.querySelector('[data-is-streaming="true"]') && !document.querySelector('[aria-label="Stop response"]')), 20000);
    await page.bringToFront();
    await type(page, "Summarize these meeting notes for the partner");
    await page.keyboard.press("Enter");
    await page2.bringToFront();
    await type(page2, "Summarize this memo into key takeaways");
    await page2.keyboard.press("Enter");
    await page.bringToFront();
    await replyDone(page);  // then send straight away: a quick follow-up must not lose the previous reply
    await type(page, "Now translate the summary in french");
    await page.keyboard.press("Enter");
    // Background tabs throttle timers, so give the other tab's reply time to finish.
    const local = await waitFor(async () => {
      const l = await readStorage(ctx);
      return l.totals && l.totals.allTime.turns >= 3 ? l : null;
    }, 20000) || await readStorage(ctx);
    assert.strictEqual(local.totals.allTime.turns, 3);
    assert.strictEqual(local.ledger.length, 3);
    assert.strictEqual(local.state.messageCount, 3);
  } finally {
    await ctx.close();
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch (e) { /* best effort */ }
  }
});
