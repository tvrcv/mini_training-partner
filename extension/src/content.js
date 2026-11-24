// Token Steward for claude.ai: watches the message box, offers a right-sizing tip before a light
// request is sent on a heavy setup, and thanks the person when a reply ran lighter than the
// reference configuration. Nothing typed or received is stored: only counts and estimates.

(function () {
  "use strict";
  const Core = globalThis.TokenStewardCore;
  const Dom = globalThis.TokenStewardDom;
  const DAY = 86400000;
  const LEDGER_MAX = 2000;

  let cfg = null;
  let dom = null;
  let ui = null;
  let store = null;
  let draft = { id: 0, tip: null, counted: false, dismissed: false };
  let inflight = null;          // the message just sent, waiting for its reply
  let bypassNextSend = false;   // set by "Send anyway" in confirm mode
  let debounce = null;

  // ---- storage ------------------------------------------------------------------------------

  const api = globalThis.chrome && chrome.storage ? chrome : null;

  function storageGet(keys) {
    return new Promise((res) => (api ? api.storage.local.get(keys, res) : res({})));
  }
  function storageSet(obj) {
    return new Promise((res) => (api ? api.storage.local.set(obj, res) : res()));
  }
  function managedPolicy() {
    return new Promise((res) => {
      try { api.storage.managed.get(null, (p) => res((api.runtime && api.runtime.lastError) ? {} : p || {})); }
      catch (e) { res({}); }
    });
  }

  async function loadStore() {
    const s = await storageGet(["prefs", "state", "totals", "ledger"]);
    return {
      prefs: s.prefs || { snoozeUntil: 0 },
      state: Object.assign({ messageCount: 0, lastTipMessage: null, lastTipTs: 0, tipsDay: "", tipsToday: 0,
                             consecutiveIgnored: 0, pending: null, lastThanksTs: 0 }, s.state || {}),
      totals: s.totals || { allTime: { cost: 0, baseline: 0, savings: 0, turns: 0 }, byMonth: {}, tipsShown: 0, tipsAccepted: 0 },
      ledger: s.ledger || []
    };
  }
  const save = (...keys) => storageSet(Object.fromEntries(keys.map((k) => [k, store[k]])));

  // Every claude.ai tab runs its own copy of this script. Each update takes a lock shared by all
  // claude.ai tabs (Web Locks are per origin), re-reads storage, applies the change and writes it
  // back, so one tab never overwrites another tab's totals or ledger.
  let queue = Promise.resolve();
  function mutate(fn) {
    const apply = async () => {
      store = await loadStore();
      const result = fn(store);
      await save("state", "totals", "ledger");
      return result;
    };
    const locked = () => (navigator.locks ? navigator.locks.request("token-steward-store", apply) : apply());
    queue = queue.then(locked).catch(() => undefined);
    return queue;
  }
  const monthKey = (t) => new Date(t).toISOString().slice(0, 7);
  const today = () => new Date().toISOString().slice(0, 10);
  const snoozed = () => Date.now() < (store.prefs.snoozeUntil || 0);

  // ---- current setup ------------------------------------------------------------------------

  function currentSetup() {
    const modelKey = Core.modelFromLabel(cfg, dom.modelLabel());
    const e = dom.effortState();
    let effort = null;
    if (e && e.level) effort = e.level;
    else if (e && e.thinking === true) effort = cfg.policy.thinkingOnEffort;
    else if (e && e.thinking === false) effort = cfg.policy.thinkingOffEffort;
    return { modelKey, effort };
  }

  function tipAllowed() {
    const p = cfg.policy, s = store.state;
    if (!p.enabled || snoozed()) return false;
    if (s.tipsDay === today() && s.tipsToday >= p.maxTipsPerDay) return false;
    if (s.consecutiveIgnored >= p.stopAfterConsecutiveIgnored) return false;
    if (s.lastTipMessage !== null) {
      if (s.messageCount + 1 - s.lastTipMessage < p.minMessagesBetweenTips) return false;
      if (Date.now() - s.lastTipTs < p.minMinutesBetweenTips * 60000) return false;
    }
    return true;
  }

  // ---- while typing -------------------------------------------------------------------------

  function onInput(ev) {
    const c = dom.composer();
    if (!c || !(c === ev.target || c.contains(ev.target))) return;
    clearTimeout(debounce);
    debounce = setTimeout(evaluateDraft, 700);
  }

  function evaluateDraft() {
    const text = dom.promptText();
    if (!text) { ui.hideTip(); draft.tip = null; return; }
    if (draft.dismissed) return;
    const { modelKey, effort } = currentSetup();
    const tip = Core.evaluateTip(cfg, text, modelKey, effort);
    if (!tip) { ui.hideTip(); draft.tip = null; return; }
    if (!draft.counted && !tipAllowed()) return;
    draft.tip = tip;
    ui.showTip(tip, dom.composerRoot(dom.composer()));
    if (!draft.counted) {
      draft.counted = true;
      mutate((st) => {
        const s = st.state;
        s.lastTipMessage = s.messageCount + 1;
        s.lastTipTs = Date.now();
        if (s.tipsDay !== today()) { s.tipsDay = today(); s.tipsToday = 0; }
        s.tipsToday += 1;
        if (tip.kind === "upgrade") {
          st.totals.upgradeTipsShown = (st.totals.upgradeTipsShown || 0) + 1;
        } else {
          s.pending = { message: s.messageCount + 1, fromTier: tip.fromTier, fromEffortRank: tip.fromEffortRank };
          st.totals.tipsShown += 1;
        }
      });
    }
  }

  // ---- on send ------------------------------------------------------------------------------

  function onKeydown(ev) {
    if (ev.key !== "Enter" || ev.shiftKey || ev.isComposing) return;
    const c = dom.composer();
    if (!c || !(c === ev.target || c.contains(ev.target))) return;
    interceptSend(ev);
  }

  function onClick(ev) {
    const btn = dom.sendButton();
    if (!btn || !(btn === ev.target || btn.contains(ev.target))) return;
    interceptSend(ev);
  }

  let lastSend = { text: null, at: 0 };  // in memory only, to ignore a duplicate event for one send

  function interceptSend(ev) {
    const text = dom.promptText();
    if (!text) return;
    if (text === lastSend.text && Date.now() - lastSend.at < 1000) return;
    if (bypassNextSend) { bypassNextSend = false; recordSend(text); return; }

    const p = cfg.policy;
    if (p.enabled && p.mode === "confirm" && !snoozed()) {
      const { modelKey, effort } = currentSetup();
      const tip = draft.tip || Core.evaluateTip(cfg, text, modelKey, effort);
      if (tip && tip.kind !== "upgrade" && tip.severity >= p.confirmMinSeverity && !draft.confirmed) {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        ui.hideTip();
        ui.confirm(tip, () => {
          draft.confirmed = true;
          bypassNextSend = true;
          const b = dom.sendButton();
          if (b) b.click();
        });
        return;
      }
    }
    recordSend(text);
  }

  function recordSend(text) {
    lastSend = { text, at: Date.now() };
    settleInflight();  // a quick follow-up must not discard the previous reply's measurement
    const { modelKey, effort } = currentSetup();
    const turn = modelKey ? { accepted: false } : null;

    mutate((st) => {
      const s = st.state;
      s.messageCount += 1;
      if (s.pending && s.messageCount > s.pending.message && modelKey) {
        const tier = Core.tierOf(cfg, modelKey), rank = Core.effortRank(cfg, effort);
        if (tier < s.pending.fromTier || (rank !== null && s.pending.fromEffortRank !== null && rank < s.pending.fromEffortRank)) {
          if (turn) turn.accepted = true;
          s.pending = null;
          s.consecutiveIgnored = 0;
          st.totals.tipsAccepted += 1;
        } else if (s.messageCount - s.pending.message >= 2) {
          s.pending = null;
          s.consecutiveIgnored += 1;
        }
      }
    });

    inflight = turn && Object.assign(turn, {
      modelKey, effort, taskClass: Core.classify(cfg, text).taskClass, tipped: !!draft.tip,
      promptChars: text.length, historyChars: dom.historyChars(), startReply: dom.lastReplyText(), startCount: dom.replyCount(),
      sentAt: Date.now(), sawStreaming: false, stableTicks: 0, lastLen: -1
    });
    draft = { id: draft.id + 1, tip: null, counted: false, dismissed: false };
    ui.hideTip();
  }

  // ---- reply finished -----------------------------------------------------------------------

  // If the previous reply has visibly finished but tick() hasn't caught it yet, record it now.
  function settleInflight() {
    if (!inflight || dom.isStreaming()) return;
    const reply = dom.lastReplyText();
    if (reply && (dom.replyCount() > inflight.startCount || reply !== inflight.startReply)) {
      const done = inflight;
      inflight = null;
      finishTurn(done, reply.length);
    }
  }

  function tick() {
    if (!inflight) return;
    const streaming = dom.isStreaming();
    if (streaming) { inflight.sawStreaming = true; return; }
    const reply = dom.lastReplyText();
    const changed = reply && (dom.replyCount() > inflight.startCount || reply !== inflight.startReply);
    if (Date.now() - inflight.sentAt > 15 * 60000) { inflight = null; return; }
    if (!changed) return;
    // Finished when streaming ended, or (if we never saw streaming) once the reply stops growing.
    if (!inflight.sawStreaming) {
      inflight.stableTicks = reply.length === inflight.lastLen ? inflight.stableTicks + 1 : 0;
      inflight.lastLen = reply.length;
      if (inflight.stableTicks < 2) return;
    }
    const done = inflight;
    inflight = null;
    finishTurn(done, reply.length);
  }

  function finishTurn(t, replyChars) {
    const priced = Core.priceTurn(cfg, { modelKey: t.modelKey, effort: t.effort, promptChars: t.promptChars,
                                         historyChars: t.historyChars, replyChars });
    const now = Date.now();
    const row = {
      v: 1, ts: now, surface: "claude.ai", model: t.modelKey, effort: t.effort, task_class: t.taskClass,
      est_tokens: priced.usage, cost: +priced.cost.toFixed(6), baseline: priced.baseKey + "@" + cfg.baseline.effort,
      baseline_cost: +priced.baselineCost.toFixed(6), savings: +priced.savings.toFixed(6),
      tipped: t.tipped, tip_accepted: t.accepted
    };
    return mutate((st) => {
      st.ledger.push(row);
      if (st.ledger.length > LEDGER_MAX) st.ledger.splice(0, st.ledger.length - LEDGER_MAX);
      const tot = st.totals;
      const before = { savings: tot.allTime.savings, rightSized: tot.allTime.rightSized || 0 };
      const m = tot.byMonth[monthKey(now)] = tot.byMonth[monthKey(now)] || { cost: 0, baseline: 0, savings: 0, turns: 0 };
      for (const b of [tot.allTime, m]) {
        b.cost += row.cost; b.baseline += row.baseline_cost; b.savings += Math.max(0, row.savings); b.turns += 1;
      }
      if (row.savings > 0) tot.allTime.rightSized = before.rightSized + 1;

      const p = cfg.policy, s = st.state;
      if (!p.enabled || snoozed()) return;
      const milestone = celebrationFor(before, tot, t.accepted);
      const cooled = now - (s.lastThanksTs || 0) >= p.thanksMinMinutesBetween * 60000;
      if (milestone || (row.savings >= p.thanksMinSavingsUsd && (t.accepted || cooled))) {
        const thanks = row.savings > 0 ? Core.thanksText(cfg, priced, t.modelKey, t.effort,
          { month: m.savings, allTime: tot.allTime.savings }, t.accepted, !!milestone) : "";
        ui.toast(milestone ? milestone.text + " " + thanks : thanks, { milestone: !!milestone, big: milestone && milestone.big });
        if (milestone && p.celebrations) ui.confetti(milestone.big);
        s.lastThanksTs = now;
      }
    });
  }

  // A savings milestone (or a first tip acted on) earns a celebration. Seat-plan firms using the
  // "allowance" framing count right-sized replies instead of dollars.
  function celebrationFor(before, tot, accepted) {
    const c = cfg.celebrations || {};
    if (!c.enabled || !cfg.policy.celebrations) return null;
    if (cfg.policy.costFraming === "allowance") {
      const n = Core.milestoneCrossed(c.milestones_right_sized_tasks, before.rightSized, tot.allTime.rightSized || 0);
      if (n) return { big: true, text: "Milestone: " + n + " right-sized replies. Thank you, this is exactly the habit that adds up." };
    } else {
      const usd = Core.milestoneCrossed(c.milestones_usd, before.savings, tot.allTime.savings);
      if (usd) return { big: true, text: "Milestone: you've now saved the firm ≈" + Core.fmtMoney(cfg, usd) + " by right-sizing your AI use. Thank you, this is exactly the habit that adds up." };
    }
    if (accepted && tot.tipsAccepted === 1) return { big: false, text: "Your first tip acted on. Thank you!" };
    return null;
  }

  // ---- UI (shadow DOM so claude.ai styles and ours never collide) ---------------------------

  function makeUi() {
    const host = document.createElement("div");
    host.id = "token-steward-root";
    document.documentElement.appendChild(host);
    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = api && api.runtime ? api.runtime.getURL("src/ui.css") : "ui.css";
    shadow.appendChild(style);

    const tip = el("div", "ts-tip", { role: "status", "aria-live": "polite", hidden: "" });
    const toastEl = el("div", "ts-toast", { role: "status", "aria-live": "polite", hidden: "" });
    shadow.append(tip, toastEl);
    let toastTimer = null;
    let anchor = null;

    function el(tag, cls, attrs) {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
      return n;
    }
    function button(label, cls, onClick) {
      const b = el("button", cls, { type: "button" });
      b.textContent = label;
      b.addEventListener("click", onClick);
      return b;
    }
    function place() {
      if (tip.hidden || !anchor) return;
      const r = anchor.getBoundingClientRect();
      const width = Math.min(r.width || 640, 680);
      tip.style.width = width + "px";
      tip.style.left = Math.max(16, r.left + (r.width - width) / 2) + "px";
      tip.style.bottom = Math.max(16, window.innerHeight - r.top + 8) + "px";
    }
    window.addEventListener("resize", place);

    return {
      showTip(t, anchorEl) {
        anchor = anchorEl;
        tip.replaceChildren(
          el("div", "ts-brand"), el("div", "ts-text"), el("div", "ts-actions"));
        tip.querySelector(".ts-brand").textContent = "Token Steward";
        const text = tip.querySelector(".ts-text");
        const strong = el("strong");
        strong.textContent = t.title + " ";
        text.append(strong, document.createTextNode(t.body + " Your choice: sending as-is is fine."));
        tip.querySelector(".ts-actions").append(
          button("Got it", "ts-btn ts-primary", () => { draft.dismissed = true; this.hideTip(); }),
          button("Pause tips for 4 hours", "ts-btn", () => {
            store.prefs.snoozeUntil = Date.now() + 4 * 3600000; save("prefs"); this.hideTip();
          }));
        tip.hidden = false;
        place();
      },
      hideTip() { tip.hidden = true; },
      toast(message, opts) {
        const milestone = !!(opts && opts.milestone);
        toastEl.classList.toggle("ts-milestone", milestone);
        toastEl.replaceChildren(el("div", "ts-brand"), el("div", "ts-text"),
          button("×", "ts-close", () => { toastEl.hidden = true; }));
        toastEl.querySelector(".ts-brand").textContent =
          milestone && opts.big ? "Token Steward · Milestone" : milestone ? "Token Steward · Thank you" : "Token Steward";
        toastEl.querySelector(".ts-text").textContent = message;
        toastEl.querySelector(".ts-close").setAttribute("aria-label", "Dismiss");
        toastEl.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { toastEl.hidden = true; }, 12000);
      },
      // Confetti on a canvas over the page; pointer-events off so nothing under it is blocked.
      // Skipped entirely for people who ask their system for reduced motion.
      confetti(big) {
        if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const canvas = el("canvas", "ts-confetti", { "aria-hidden": "true" });
        shadow.append(canvas);
        const dpr = window.devicePixelRatio || 1;
        const W = window.innerWidth, H = window.innerHeight;
        canvas.width = W * dpr; canvas.height = H * dpr;
        const ctx = canvas.getContext("2d");
        if (!ctx) { canvas.remove(); return; }
        ctx.scale(dpr, dpr);
        const colors = ["#2f5d50", "#7fb8a4", "#e0a458", "#d9534f", "#5b8def", "#f2d06b", "#b07cc6"];
        const count = big ? 160 : 50;
        const parts = Array.from({ length: count }, (_, i) => {
          const fromLeft = i % 2 === 0;
          return {
            x: fromLeft ? W * 0.15 : W * 0.85, y: H * 0.75,
            vx: (fromLeft ? 1 : -1) * (3 + Math.random() * 6), vy: -(9 + Math.random() * 8),
            w: 6 + Math.random() * 6, h: 3 + Math.random() * 4,
            r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
            c: colors[i % colors.length]
          };
        });
        const start = performance.now(), duration = big ? 2600 : 1600;
        function frame(now) {
          const t = now - start;
          ctx.clearRect(0, 0, W, H);
          ctx.globalAlpha = Math.max(0, 1 - Math.max(0, t - duration * 0.6) / (duration * 0.4));
          for (const p of parts) {
            p.vy += 0.35; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
            ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r);
            ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            ctx.restore();
          }
          if (t < duration) requestAnimationFrame(frame); else canvas.remove();
        }
        requestAnimationFrame(frame);
      },
      confirm(t, onSendAnyway) {
        const backdrop = el("div", "ts-backdrop");
        const dlg = el("div", "ts-dialog", { role: "dialog", "aria-modal": "true", "aria-labelledby": "ts-dlg-title" });
        const h = el("h2", "", { id: "ts-dlg-title" });
        h.textContent = t.title;
        const p = el("p");
        p.textContent = t.body;
        const close = () => backdrop.remove();
        const switchBtn = button("I'll switch first", "ts-btn ts-primary", close);
        const sendBtn = button("Send as-is", "ts-btn", () => { close(); onSendAnyway(); });
        const actions = el("div", "ts-actions");
        actions.append(switchBtn, sendBtn);
        dlg.append(el("div", "ts-brand"), h, p, actions);
        dlg.querySelector(".ts-brand").textContent = "Token Steward";
        backdrop.append(dlg);
        backdrop.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
        shadow.append(backdrop);
        switchBtn.focus();
      }
    };
  }

  // ---- boot ---------------------------------------------------------------------------------

  async function boot() {
    const policy = await managedPolicy();
    cfg = Core.buildConfig(globalThis.TOKEN_STEWARD_SHARED, policy);
    dom = Dom.makeAdapter(cfg.policy.selectors);
    store = await loadStore();
    ui = makeUi();
    document.addEventListener("input", onInput, true);
    document.addEventListener("keydown", onKeydown, true);
    document.addEventListener("click", onClick, true);
    setInterval(tick, 1000);
    if (api && api.storage.onChanged) {
      api.storage.onChanged.addListener((changes, area) => {
        if (area !== "local") return;
        for (const key of ["prefs", "state", "totals", "ledger"]) {
          if (changes[key] && changes[key].newValue) store[key] = changes[key].newValue;  // other tabs, popup
        }
        if (changes.prefs && snoozed()) ui.hideTip();
      });
    }
    globalThis.__tokenStewardReady = true;
  }

  boot();
})();
