(async function () {
  "use strict";
  const Core = globalThis.TokenStewardCore;
  const get = (area, keys) => new Promise((r) => { try { chrome.storage[area].get(keys, (v) => r(v || {})); } catch (e) { r({}); } });
  const policy = await get("managed", null);
  const cfg = Core.buildConfig(globalThis.TOKEN_STEWARD_SHARED, policy);
  const { totals, ledger = [], prefs = {} } = await get("local", ["totals", "ledger", "prefs"]);
  const money = (x) => Core.fmtMoney(cfg, x || 0);
  const $ = (id) => document.getElementById(id);
  const baseLabel = Core.labelOf(cfg, Core.modelFromLabel(cfg, cfg.baseline.model) || cfg.baseline.model);

  $("baseline").textContent = "Compared with " + baseLabel + " at " + cfg.baseline.effort + " effort";
  const month = totals && totals.byMonth[new Date().toISOString().slice(0, 7)];
  if (cfg.policy.costFraming === "allowance") {
    const ratio = (b) => (b && b.cost > 0 ? Math.max(1, b.baseline / b.cost).toFixed(1) + "× lighter" : "–");
    $("month").textContent = ratio(month);
    $("all").textContent = ratio(totals && totals.allTime);
    $("note").textContent = "Usage relative to the reference setup, estimated from on-screen text. Nothing you type is stored.";
  } else {
    $("month").textContent = "≈" + money(month && month.savings);
    $("all").textContent = "≈" + money(totals && totals.allTime.savings);
  }
  $("turns").textContent = totals ? totals.allTime.turns : 0;
  $("tips").textContent = totals ? totals.tipsAccepted + " / " + totals.tipsShown : "0 / 0";

  const recent = ledger.slice(-300);
  const counts = {};
  for (const r of recent) counts[r.model] = (counts[r.model] || 0) + 1;
  const body = document.querySelector("#mix tbody");
  for (const [model, n] of Object.entries(counts).sort((a, b) => b[1] - a[1])) {
    const tr = document.createElement("tr");
    for (const v of [Core.labelOf(cfg, model), n, Math.round((100 * n) / recent.length) + "%"]) {
      const td = document.createElement("td"); td.textContent = v; tr.append(td);
    }
    body.append(tr);
  }

  const snoozeBtn = $("snooze");
  const paused = Date.now() < (prefs.snoozeUntil || 0);
  snoozeBtn.textContent = paused ? "Resume tips" : "Pause tips for 4 hours";
  snoozeBtn.addEventListener("click", () => {
    const next = Object.assign({}, prefs, { snoozeUntil: paused ? 0 : Date.now() + 4 * 3600000 });
    chrome.storage.local.set({ prefs: next }, () => window.close());
  });

  $("export").addEventListener("click", () => {
    const cols = ["date", "model", "effort", "task_class", "est_input", "est_output", "cost", "baseline", "baseline_cost", "savings", "tipped", "tip_accepted"];
    const lines = [cols.join(",")].concat(ledger.map((r) => [new Date(r.ts).toISOString(), r.model, r.effort, r.task_class,
      r.est_tokens.input + r.est_tokens.cache_read + r.est_tokens.cache_write, r.est_tokens.output, r.cost, r.baseline,
      r.baseline_cost, r.savings, r.tipped, r.tip_accepted].join(",")));
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "token-steward-claude-ai.csv" });
    a.click();
    URL.revokeObjectURL(url);
  });
})();
