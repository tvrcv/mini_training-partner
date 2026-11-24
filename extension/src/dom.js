// Token Steward page adapter for claude.ai.
//
// Everything that depends on claude.ai's page structure is in this file. claude.ai is not a
// public API and its markup changes without notice, so every lookup:
//   * tries an admin-supplied selector first (managed policy "selectors"), then several fallbacks
//   * returns null when unsure, and the content script stays silent on null
// If tips stop appearing after a claude.ai update, this is the file to fix (or push new
// selectors through policy without shipping a new version).

(function (root) {
  "use strict";

  const DEFAULT_SELECTORS = {
    composer: [
      'div[contenteditable="true"].ProseMirror',
      'fieldset div[contenteditable="true"]',
      'div[contenteditable="true"][role="textbox"]',
      'textarea[data-testid="chat-input"]',
      "textarea"
    ],
    sendButton: [
      'button[aria-label="Send message"]',
      'button[aria-label*="Send" i]',
      'button[type="submit"]'
    ],
    stopButton: ['button[aria-label*="Stop" i]'],
    modelSelector: [
      '[data-testid="model-selector-dropdown"]',
      'button[aria-label*="model" i]',
      'button[aria-haspopup="menu"]'
    ],
    effortControl: [
      '[data-testid*="effort" i]',
      'button[aria-label*="effort" i]',
      '[data-testid*="thinking" i]',
      'button[aria-label*="thinking" i]'
    ],
    assistantMessage: [
      "[data-is-streaming]",
      '[data-testid="assistant-message"]',
      ".font-claude-message",
      ".font-claude-response"
    ],
    userMessage: ['[data-testid="user-message"]', ".font-user-message"]
  };

  const MODEL_RE = /\b(?:claude\s+)?(haiku|sonnet|opus|fable|mythos)(?:\s+(\d+(?:\.\d+)?))?\b/i;
  const EFFORT_RE = /\b(low|medium|high|xhigh|max)\b/i;

  function makeAdapter(overrides) {
    const sel = {};
    for (const [k, list] of Object.entries(DEFAULT_SELECTORS)) {
      const o = overrides && overrides[k];
      sel[k] = (Array.isArray(o) ? o : o ? [o] : []).concat(list);
    }

    function visible(el) {
      if (!el || !el.isConnected) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }

    function first(key, scope) {
      for (const s of sel[key]) {
        let nodes;
        try { nodes = (scope || document).querySelectorAll(s); } catch (e) { continue; }
        for (const n of nodes) if (visible(n)) return n;
      }
      return null;
    }

    function all(key) {
      for (const s of sel[key]) {
        let nodes;
        try { nodes = document.querySelectorAll(s); } catch (e) { continue; }
        if (nodes.length) return Array.from(nodes);
      }
      return [];
    }

    // The form/fieldset/container that holds the message box and its controls.
    function composerRoot(composer) {
      let el = composer;
      for (let i = 0; el && i < 8; i++) {
        if (el.tagName === "FIELDSET" || el.tagName === "FORM") return el;
        if (el.querySelector && el.querySelectorAll("button").length >= 3) return el;
        el = el.parentElement;
      }
      return composer ? composer.parentElement : document.body;
    }

    function composer() { return first("composer"); }

    function promptText(c) {
      c = c || composer();
      if (!c) return "";
      return (c.value !== undefined && c.tagName === "TEXTAREA" ? c.value : c.innerText || "").trim();
    }

    function modelLabel() {
      const c = composer();
      const scope = c ? composerRoot(c) : document;
      const candidates = [first("modelSelector", scope), first("modelSelector")].filter(Boolean);
      for (const el of candidates) {
        const m = (el.innerText || el.getAttribute("aria-label") || "").match(MODEL_RE);
        if (m) return m[0];
      }
      // Last resort: any button near the message box whose text names a model family.
      for (const b of scope.querySelectorAll("button")) {
        const m = (b.innerText || "").match(MODEL_RE);
        if (m && visible(b)) return m[0];
      }
      return null;
    }

    // Returns an explicit effort level, or {thinking: true|false}, or null if unknown.
    function effortState() {
      const c = composer();
      const scope = c ? composerRoot(c) : document;
      // Composer area only: a page-wide search could pick up "thinking" sections inside replies.
      const el = first("effortControl", scope);
      if (!el) return null;
      const text = (el.innerText || "") + " " + (el.getAttribute("aria-label") || "");
      const level = text.match(EFFORT_RE);
      if (level) return { level: level[1].toLowerCase() };
      const pressed = el.getAttribute("aria-pressed") || el.getAttribute("aria-checked") ||
        (el.querySelector("[aria-checked]") || { getAttribute: () => null }).getAttribute("aria-checked");
      if (pressed === "true") return { thinking: true };
      if (pressed === "false") return { thinking: false };
      return null;
    }

    function isStreaming() {
      if (document.querySelector('[data-is-streaming="true"]')) return true;
      const c = composer();
      // Only a stop button next to the message box counts; other "Stop …" buttons on the page don't.
      return !!(c && first("stopButton", composerRoot(c)));
    }

    function replyCount() { return all("assistantMessage").length; }

    function lastReplyText() {
      const msgs = all("assistantMessage");
      return msgs.length ? (msgs[msgs.length - 1].innerText || "") : "";
    }

    // Characters of the conversation before the latest exchange (what gets re-sent as context).
    function historyChars() {
      const nodes = all("assistantMessage").concat(all("userMessage"));
      const total = nodes.reduce((n, el) => n + (el.innerText || "").length, 0);
      return Math.max(0, total - lastReplyText().length);
    }

    function sendButton() { return first("sendButton", composerRoot(composer())) || first("sendButton"); }

    return { composer, composerRoot, promptText, modelLabel, effortState, isStreaming, lastReplyText, replyCount,
             historyChars, sendButton, selectors: sel };
  }

  root.TokenStewardDom = { makeAdapter, DEFAULT_SELECTORS };
})(globalThis);
