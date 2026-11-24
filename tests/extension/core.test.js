// Run: node --test tests/extension/
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..", "..");
require(path.join(ROOT, "extension/src/shared-config.js"));
const Core = require(path.join(ROOT, "extension/src/core.js"));
const cfg = Core.buildConfig(globalThis.TOKEN_STEWARD_SHARED, {});

const PROMPTS = [
  "Rephrase this email to the client so it sounds more formal",
  "translate this paragraph in french",
  "Summarize these meeting notes into key takeaways for the partner",
  "Design the system architecture for our pricing engine and walk through the trade-offs",
  "We have an intermittent race condition in the scheduler, find the root cause",
  "why does the auth test fail on CI",
  "yes go ahead",
  "/compact",
  "What is a DCF",
  "Fix the typo in this slide title please",
  "Write an excel formula that does a vlookup across two tabs",
  "Build a market sizing model for the EU cold-chain logistics market with scenario analysis",
];

test("JS classifier agrees with the Python plugin classifier", () => {
  const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, "plugins/token-steward/scripts"))})
from steward import classifier, config
cfg = config.load_config()
print(json.dumps([classifier.classify(cfg, p)[0] for p in json.load(sys.stdin)]))`;
  const expected = JSON.parse(execFileSync("python3", ["-c", py], { input: JSON.stringify(PROMPTS) }).toString());
  const actual = PROMPTS.map((p) => Core.classify(cfg, p).taskClass);
  assert.deepStrictEqual(actual, expected);
});

test("model labels from the claude.ai menu resolve", () => {
  assert.strictEqual(Core.modelFromLabel(cfg, "Opus 5.5"), "claude-opus-5-5");
  assert.strictEqual(Core.modelFromLabel(cfg, "Claude Sonnet 5.5"), "claude-sonnet-5-5");
  assert.strictEqual(Core.modelFromLabel(cfg, "Opus 5"), "claude-opus-5");
  assert.strictEqual(Core.modelFromLabel(cfg, "Haiku"), "claude-haiku-5-5");
  assert.strictEqual(Core.modelFromLabel(cfg, "Fable 5.2"), "claude-fable-5-2");
  assert.strictEqual(Core.modelFromLabel(cfg, "Projects"), null);
});

test("tips: light work on a heavy setup, silence otherwise", () => {
  const t = Core.evaluateTip(cfg, "Rephrase this email so it sounds more formal", "claude-opus-5-5", "high");
  assert.ok(t);
  assert.match(t.body, /pick Haiku in the model menu/);
  assert.match(t.body, /lower cost/);
  assert.strictEqual(Core.evaluateTip(cfg, "Rephrase this email so it sounds more formal", "claude-haiku-5-5", "low"), null);
  assert.strictEqual(Core.evaluateTip(cfg, "Design the system architecture for the data platform", "claude-opus-5-5", "high"), null);
  assert.strictEqual(Core.evaluateTip(cfg, "why does the auth test fail", "claude-opus-5-5", "high"), null);
  assert.strictEqual(Core.evaluateTip(cfg, "Rephrase this email", null, "high"), null); // unknown model: stay quiet
});

test("allowance framing never quotes dollars", () => {
  const c2 = Core.buildConfig(globalThis.TOKEN_STEWARD_SHARED, { costFraming: "allowance" });
  const t = Core.evaluateTip(c2, "Proofread this paragraph please", "claude-opus-5-5", "high");
  assert.match(t.body, /usage allowance/);
  assert.doesNotMatch(t.body, /\$/);
  const priced = Core.priceTurn(c2, { modelKey: "claude-haiku-5-5", effort: "low", promptChars: 400, historyChars: 2000, replyChars: 1200 });
  assert.doesNotMatch(Core.thanksText(c2, priced, "claude-haiku-5-5", "low", { month: 1, allTime: 2 }, true), /\$/);
});

test("pricing a turn: lighter than reference saves, reference saves nothing", () => {
  const args = { effort: "low", promptChars: 400, historyChars: 8000, replyChars: 1500 };
  const light = Core.priceTurn(cfg, Object.assign({ modelKey: "claude-sonnet-5-5" }, args));
  assert.ok(light.savings > 0 && light.cost > 0);
  const ref = Core.priceTurn(cfg, Object.assign({}, args, { modelKey: "claude-opus-5-5", effort: "high" }));
  assert.ok(Math.abs(ref.savings) < 1e-12);
});

test("extension config is in sync with the plugin's defaults.json", () => {
  const defaults = JSON.parse(require("node:fs").readFileSync(
    path.join(ROOT, "plugins/token-steward/config/defaults.json"), "utf8"));
  const shared = globalThis.TOKEN_STEWARD_SHARED;
  const strip = (o) => JSON.parse(JSON.stringify(o, (k, v) => (k.startsWith("_") ? undefined : v)));
  for (const key of ["pricing", "baseline", "recommendations", "classifier", "effort_output_multiplier"]) {
    assert.deepStrictEqual(shared[key], strip(defaults[key]),
      `${key} differs: run python3 tools/build_extension_config.py`);
  }
});
