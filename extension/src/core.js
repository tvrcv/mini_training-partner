// Token Steward core logic for claude.ai: pure functions, no DOM, no chrome.* APIs.
// Mirrors plugins/token-steward/scripts/steward/{classifier,pricing}.py so both surfaces
// classify and price the same way. Loaded as a content script and by the Node tests.

(function (root) {
  "use strict";

  // Extension-only defaults. Admins override any of these through Chrome/Edge managed policy
  // (see managed_schema.json); users can't.
  const POLICY_DEFAULTS = {
    enabled: true,
    mode: "inline",               // "inline": tip beside the message box, never blocks. "confirm": also hold severe mismatches once on send.
    costFraming: "dollars",       // "dollars" (usage-based billing) or "allowance" (seat plans: talk about usage limits, not money)
    baselineModel: null,          // null = use shared config baseline
    baselineEffort: null,
    minSeverity: 2,
    confirmMinSeverity: 5,
    minMessagesBetweenTips: 3,
    minMinutesBetweenTips: 10,
    maxTipsPerDay: 8,
    stopAfterConsecutiveIgnored: 3,
    thanksMinSavingsUsd: 0.01,
    thanksMinMinutesBetween: 15,
    charsPerToken: 4,
    thinkingOffEffort: "low",     // what "extended thinking off" counts as
    thinkingOnEffort: "high",     // what "extended thinking on" counts as when no explicit level is shown
    selectors: {}                 // optional DOM selector overrides, see dom.js
  };

  const CLASS_PHRASES = { trivial: "a quick, lightweight request", routine: "a routine request" };

  function buildConfig(shared, policy) {
    const p = Object.assign({}, POLICY_DEFAULTS, policy || {});
    const baseline = {
      model: p.baselineModel || shared.baseline.model,
      effort: p.baselineEffort || shared.baseline.effort
    };
    return Object.assign({}, shared, { policy: p, baseline: baseline });
  }

  // ---- classification (port of classifier.py) -------------------------------------------

  const CODE_FENCE = /```/g;
  const FILE_REF = /(@[\w./-]+|\b[\w-]+\.(py|ts|tsx|js|java|go|rs|sql|ipynb|xlsx|pptx|docx|csv)\b)/gi;
  const regexCache = new Map();

  function rx(pattern) {
    if (!regexCache.has(pattern)) regexCache.set(pattern, new RegExp(pattern, "im"));
    return regexCache.get(pattern);
  }

  function classify(cfg, prompt) {
    const c = cfg.classifier;
    const text = (prompt || "").trim();
    const words = text ? text.split(/\s+/).length : 0;
    let score = 0;
    const matched = [];

    for (const s of c.signals) {
      if (rx(s.pattern).test(text)) {
        score += s.weight;
        matched.push(s.name);
      }
    }
    const isMatched = (sign) => c.signals.some((s) => Math.sign(s.weight) === sign && matched.includes(s.name));
    const heavy = isMatched(1);
    const light = isMatched(-1);

    if (words <= c.short_prompt_words && !heavy) score -= 1;
    else if (words >= c.long_prompt_words) { score += 2; matched.push("long, detailed brief"); }

    const fences = Math.floor((text.match(CODE_FENCE) || []).length / 2);
    const files = new Set((text.match(FILE_REF) || [])).size;
    if (fences >= 2 || files >= 4) { score += 2; matched.push("multiple files / code blocks"); }

    if (text.startsWith("/") || words <= 3) return { taskClass: "continuation", score, matched };

    let taskClass = "general";
    if (score >= c.complex_min_score) taskClass = "complex";
    else if (light && score <= c.trivial_max_score) taskClass = "trivial";
    else if (light && score <= c.routine_max_score) taskClass = "routine";
    return { taskClass, score, matched };
  }

  // ---- models, effort and money ----------------------------------------------------------

  // Resolve what the claude.ai model menu shows ("Opus 5.5", "Claude Sonnet 5.5", "Haiku") to a
  // pricing key. Exact label wins; a bare family name maps through the alias table.
  function modelFromLabel(cfg, label) {
    if (!label) return null;
    const text = String(label).toLowerCase();
    let best = null;
    for (const [key, info] of Object.entries(cfg.pricing)) {
      const l = info.label.toLowerCase();
      const re = new RegExp("\\b" + l.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\d.])");
      if (re.test(text) && (!best || l.length > cfg.pricing[best].label.length)) best = key;
    }
    if (best) return best;
    if (cfg.pricing[text]) return text;
    const family = text.match(/\b(haiku|sonnet|opus|fable|mythos)\b/);
    if (family) return cfg.aliases[family[1]] || (family[1] === "mythos" ? cfg.aliases.fable : null) || null;
    return null;
  }

  const tierOf = (cfg, key) => (key ? cfg.pricing[key].tier : null);
  const labelOf = (cfg, key) => (key ? cfg.pricing[key].label : "unknown model");
  const effortRank = (cfg, e) => { const i = cfg.effort_levels.indexOf(e); return i < 0 ? null : i; };
  const mult = (cfg, e) => cfg.effort_output_multiplier[e || "medium"] || 1.0;
  const modelForTier = (cfg, tier) => cfg.aliases[cfg.tier_names[String(tier)].toLowerCase()];

  function cost(cfg, key, usage) {
    if (!key) return 0;
    const r = cfg.pricing[key];
    return ((usage.input || 0) * r.input + (usage.output || 0) * r.output +
            (usage.cache_write || 0) * r.cache_write + (usage.cache_read || 0) * r.cache_read) / 1e6;
  }

  function counterfactualCost(cfg, usage, actualEffort, targetKey, targetEffort) {
    const scale = mult(cfg, targetEffort) / Math.max(mult(cfg, actualEffort), 1e-9);
    return cost(cfg, targetKey, Object.assign({}, usage, { output: (usage.output || 0) * scale }));
  }

  // claude.ai doesn't show token counts, so a chat turn is estimated from on-screen text:
  //  - the new message is fresh input; earlier conversation is re-sent, typically from cache
  //  - hidden reasoning is estimated from the visible reply, scaled by effort
  function estimateChatUsage(cfg, { promptChars, historyChars, replyChars, effort }) {
    const cpt = cfg.policy.charsPerToken;
    const visible = replyChars / cpt;
    return {
      input: Math.round(promptChars / cpt) + 3000,          // + system prompt and tool definitions, roughly
      cache_read: Math.round(historyChars / cpt),
      cache_write: Math.round((promptChars + replyChars) / cpt),
      output: Math.round(visible * (mult(cfg, effort) / mult(cfg, "low")))
    };
  }

  function severity(cfg, modelKey, effort, rec) {
    const modelGap = Math.max(0, tierOf(cfg, modelKey) - rec.tier);
    const cur = effortRank(cfg, effort);
    const effortGap = cur === null ? 0 : Math.max(0, cur - effortRank(cfg, rec.effort));
    return { severity: 2 * modelGap + effortGap, modelGap, effortGap };
  }

  function fmtMoney(cfg, x) {
    const s = cfg.currency_symbol || "$";
    if (Math.abs(x) >= 100) return s + Math.round(x).toLocaleString("en-US");
    if (Math.abs(x) >= 0.01) return s + x.toFixed(2);
    return "<" + s + "0.01";
  }

  // ---- decisions and wording ---------------------------------------------------------------

  // Returns null (stay quiet) or a tip: {severity, text, recModel, recEffort, fromTier, fromEffortRank}.
  function evaluateTip(cfg, prompt, modelKey, effort) {
    if (!modelKey) return null;
    const { taskClass, matched } = classify(cfg, prompt);
    const rec = cfg.recommendations[taskClass];
    if (!rec) return null;
    const sev = severity(cfg, modelKey, effort, rec);
    if (sev.severity < cfg.policy.minSeverity) return null;

    const recModel = sev.modelGap ? modelForTier(cfg, rec.tier) : modelKey;
    const recEffort = sev.effortGap ? rec.effort : effort;
    const lightSignals = matched.filter((m) => cfg.classifier.signals.some((s) => s.name === m && s.weight < 0));
    let what = CLASS_PHRASES[taskClass];
    if (lightSignals.length) what += " (" + lightSignals.slice(0, 2).join(", ") + ")";

    const current = labelOf(cfg, modelKey) + (effort ? " at " + effort + " effort" : "");
    const target = labelOf(cfg, recModel) + (sev.effortGap ? " with " + (recEffort === "low" ? "extended thinking off" : recEffort + " effort") : "");
    const ratio = estimateRatio(cfg, modelKey, effort, recModel, recEffort);
    let saving = "";
    if (ratio >= 1.5) {
      saving = cfg.policy.costFraming === "allowance"
        ? ", and uses roughly " + Math.round(ratio) + "× less of your usage allowance"
        : ", at about " + Math.round(100 * (1 - 1 / ratio)) + "% lower cost";
    }
    const steps = [];
    if (sev.modelGap) steps.push("pick " + cfg.tier_names[String(rec.tier)] + " in the model menu");
    if (sev.effortGap) steps.push(recEffort === "low" ? "turn extended thinking off" : "set effort to " + recEffort);

    return {
      severity: sev.severity,
      taskClass,
      recModel,
      recEffort,
      fromTier: tierOf(cfg, modelKey),
      fromEffortRank: effortRank(cfg, effort),
      title: "This looks like " + what + ".",
      body: "You're on " + current + ", which is built for complex, multi-step work. " + target +
            " typically handles this just as well" + saving + ". To switch: " + steps.join(", then ") + "."
    };
  }

  function estimateRatio(cfg, fromKey, fromEffort, toKey, toEffort) {
    const usage = { input: 4000, cache_read: 8000, cache_write: 1000, output: 1500 };
    const a = counterfactualCost(cfg, usage, "medium", fromKey, fromEffort || "medium");
    const b = counterfactualCost(cfg, usage, "medium", toKey, toEffort || "medium");
    return b > 0 ? a / b : 1;
  }

  // Price a finished chat turn and compare with the reference configuration.
  function priceTurn(cfg, { modelKey, effort, promptChars, historyChars, replyChars }) {
    const usage = estimateChatUsage(cfg, { promptChars, historyChars, replyChars, effort });
    const baseKey = modelFromLabel(cfg, cfg.baseline.model) || cfg.baseline.model;
    const actual = cost(cfg, modelKey, usage);
    const reference = counterfactualCost(cfg, usage, effort, baseKey, cfg.baseline.effort);
    return { usage, cost: actual, baselineCost: reference, savings: reference - actual, baseKey };
  }

  function thanksText(cfg, priced, modelKey, effort, totals, accepted) {
    const opener = accepted ? "Thanks for switching, and for considering your usage." : "Thank you for considering your usage.";
    const base = labelOf(cfg, priced.baseKey) + " at " + cfg.baseline.effort + " effort";
    if (cfg.policy.costFraming === "allowance") {
      const ratio = priced.cost > 0 ? priced.baselineCost / priced.cost : 1;
      return opener + " That reply on " + labelOf(cfg, modelKey) + " used roughly " + Math.max(1, Math.round(ratio)) +
        "× less of your usage allowance than " + base + " would have (estimate).";
    }
    return opener + " That reply on " + labelOf(cfg, modelKey) + " cost " + (priced.cost < 0.01 ? "under " + (cfg.currency_symbol || "$") + "0.01" : "about " + fmtMoney(cfg, priced.cost)) +
      ", roughly " + fmtMoney(cfg, priced.savings) + " less than " + base + ". You've saved the business ≈" +
      fmtMoney(cfg, totals.month) + " this month and ≈" + fmtMoney(cfg, totals.allTime) + " in total (estimates at API list prices).";
  }

  root.TokenStewardCore = {
    POLICY_DEFAULTS, buildConfig, classify, modelFromLabel, tierOf, labelOf, effortRank, cost,
    counterfactualCost, estimateChatUsage, severity, evaluateTip, priceTurn, thanksText, fmtMoney
  };
  if (typeof module !== "undefined") module.exports = root.TokenStewardCore;
})(typeof globalThis !== "undefined" ? globalThis : this);
