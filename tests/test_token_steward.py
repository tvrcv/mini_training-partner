"""End-to-end tests: drive the hooks exactly as Claude Code would (JSON on stdin, JSON on stdout)."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "token-steward"
CLI = ROOT / "scripts" / "token_steward.py"
sys.path.insert(0, str(ROOT / "scripts"))

from steward import classifier, config, pricing  # noqa: E402

warnings.simplefilter("ignore", ResourceWarning)


class Session:
    """A fake Claude Code session with its own HOME, plugin data dir and transcript."""

    def __init__(self, settings=None):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "home"
        (self.home / ".claude").mkdir(parents=True)
        if settings:
            (self.home / ".claude" / "settings.json").write_text(json.dumps(settings))
        self.data = base / "data"
        self.cwd = base / "proj"
        self.cwd.mkdir()
        self.transcript = base / "t.jsonl"
        self.transcript.touch()
        self.sid = "sess-1"
        self.n = 0

    def env(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_MODEL", "CLAUDE_CODE_EFFORT_LEVEL", "TOKEN_STEWARD_CONFIG")}
        env.update(HOME=str(self.home), CLAUDE_PLUGIN_DATA=str(self.data), TOKEN_STEWARD_DEBUG="1")
        return env

    def hook(self, event, **extra):
        payload = {"session_id": self.sid, "transcript_path": str(self.transcript), "cwd": str(self.cwd),
                   "hook_event_name": event, **extra}
        name = {"SessionStart": "session-start", "UserPromptSubmit": "user-prompt-submit", "Stop": "stop"}[event]
        res = subprocess.run([sys.executable, str(CLI), "hook", name], input=json.dumps(payload),
                             capture_output=True, text=True, env=self.env(), timeout=20)
        self.last_stderr = res.stderr
        assert res.returncode == 0, res.stderr
        return json.loads(res.stdout) if res.stdout.strip() else {}

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True,
                              env=self.env(), timeout=20).stdout

    def respond(self, model, inp=2000, out=800, cr=30000, cw=0, chunks=2):
        """Append one assistant API response (split over several lines, like the real transcript)."""
        self.n += 1
        with open(self.transcript, "a") as fh:
            for _ in range(chunks):
                fh.write(json.dumps({
                    "type": "assistant", "timestamp": "2026-11-24T10:00:00Z",
                    "message": {"id": f"msg_{self.n}", "model": model, "usage": {
                        "input_tokens": inp, "output_tokens": out,
                        "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}}}) + "\n")

    def user(self, text):
        with open(self.transcript, "a") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")

    def turn(self, prompt, model, effort, **usage):
        out_prompt = self.hook("UserPromptSubmit", prompt=prompt)
        self.user(prompt)
        self.respond(model, **usage)
        out_stop = self.hook("Stop", effort={"level": effort}, stop_hook_active=False)
        return out_prompt, out_stop

    def ledger(self):
        p = self.data / "ledger.jsonl"
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


class ClassifierTests(unittest.TestCase):
    cfg = config.load_config()

    def cls(self, text):
        return classifier.classify(self.cfg, text)[0]

    def test_light_work(self):
        self.assertEqual(self.cls("Rephrase this email to the client so it sounds more formal"), "trivial")
        self.assertEqual(self.cls("translate this paragraph in french"), "trivial")
        self.assertEqual(self.cls("Summarize these meeting notes into key takeaways for the partner"), "routine")

    def test_heavy_work(self):
        self.assertEqual(self.cls("Design the system architecture for our pricing engine and walk through "
                                  "the trade-offs between event sourcing and CRUD"), "complex")
        self.assertEqual(self.cls("We have an intermittent race condition in the scheduler, find the root cause"), "complex")

    def test_ambiguous_stays_quiet(self):
        self.assertEqual(self.cls("why does the auth test fail on CI"), "general")
        self.assertEqual(self.cls("yes go ahead"), "continuation")
        self.assertEqual(self.cls("/compact"), "continuation")


class PricingTests(unittest.TestCase):
    cfg = config.load_config()

    def test_resolution(self):
        r = lambda m: pricing.resolve_model(self.cfg, m)  # noqa: E731
        self.assertEqual(r("claude-opus-5-5[1m]"), "claude-opus-5-5")
        self.assertEqual(r("opus"), "claude-opus-5-5")
        self.assertEqual(r("us.anthropic.claude-sonnet-5-5"), "claude-sonnet-5-5")
        self.assertEqual(r("claude-opus-5"), "claude-opus-5")
        self.assertIsNone(r("gpt-5"))

    def test_cost(self):
        c = pricing.cost(self.cfg, "claude-opus-5-5", {"input": 1_000_000, "output": 1_000_000})
        self.assertAlmostEqual(c, 24.0)

    def test_counterfactual_effort_scaling(self):
        u = {"input": 0, "output": 1_000_000, "cache_write": 0, "cache_read": 0}
        # 1M output tokens at medium on Sonnet would be 1.5M at high on Opus: 1.5 * $20
        self.assertAlmostEqual(pricing.counterfactual_cost(self.cfg, u, "medium", "claude-opus-5-5", "high"), 30.0)


class HookFlowTests(unittest.TestCase):
    def test_nudge_then_switch_then_thanks(self):
        s = Session(settings={"model": "opus"})
        start = s.hook("SessionStart", source="startup", model="claude-opus-5-5")
        self.assertIn("Match the model to the task", start["systemMessage"])

        # First request: real work on Opus, no tip.
        p, _ = s.turn("Design the data model for the engagement tracker and explain the trade-offs",
                      "claude-opus-5-5", "high")
        self.assertEqual(p, {})

        # Light request on Opus @ high: a tip, never a block.
        p, stop = s.turn("Rephrase this email to the client so it sounds more formal", "claude-opus-5-5", "high")
        self.assertIn("systemMessage", p)
        self.assertNotIn("decision", p)
        self.assertIn("/model haiku", p["systemMessage"])
        self.assertIn("running as-is", p["systemMessage"])
        self.assertNotIn("systemMessage", stop)  # ran at baseline: nothing saved, nothing claimed

        # User follows the tip; the next completed task is thanked and counted as accepted.
        _, stop = s.turn("Now shorten the second paragraph", "claude-haiku-5-5", "low")
        self.assertIn("Thanks for switching", stop["systemMessage"])
        self.assertIn("Opus 5.5 @ high", stop["systemMessage"])
        rows = s.ledger()
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[-1]["nudge_accepted"])
        self.assertGreater(rows[-1]["savings"], 0)
        self.assertEqual(rows[0]["savings"], 0)  # baseline config itself saves nothing

        report = s.cli("report")
        self.assertIn("All time", report)
        self.assertIn("acted on: 1", report)

    def test_cooldown_and_backoff(self):
        s = Session()
        s.hook("SessionStart", source="startup", model="claude-opus-5-5")
        shown = 0
        for i in range(20):
            p, _ = s.turn(f"proofread this sentence number {i} please", "claude-opus-5-5", "high")
            shown += "systemMessage" in p
        # min_prompts_between_nudges + back-off after 3 ignored tips keeps this sparse.
        self.assertLessEqual(shown, 3)
        self.assertGreaterEqual(shown, 1)

    def test_no_nudge_on_right_sized_or_complex(self):
        s = Session()
        p, _ = s.turn("Rephrase this email so it sounds friendlier", "claude-haiku-5-5", "low")
        self.assertEqual(p, {})
        p, _ = s.turn("Rephrase this email to be warmer", "claude-haiku-5-5", "low")
        self.assertEqual(p, {})

    def test_snooze_silences(self):
        s = Session()
        s.cli("snooze", "2")
        s.turn("warm-up question about the deck", "claude-opus-5-5", "high")
        p, _ = s.turn("Rephrase this email to the client so it sounds more formal", "claude-opus-5-5", "high")
        self.assertEqual(p, {})
        self.assertEqual(len(s.ledger()), 2)  # still measured

    def test_confirm_mode_holds_once(self):
        s = Session()
        override = Path(s.tmp.name) / "org.json"
        override.write_text(json.dumps({"nudge": {"mode": "confirm"}}))
        os.environ["TOKEN_STEWARD_CONFIG"] = str(override)
        try:
            env = s.env()
            env["TOKEN_STEWARD_CONFIG"] = str(override)
            s.env = lambda: env
            s.turn("warm-up question about the deck", "claude-opus-5-5", "max")
            prompt = "Fix the typo in this slide title please"
            first = s.hook("UserPromptSubmit", prompt=prompt)
            self.assertEqual(first.get("decision"), "block")
            again = s.hook("UserPromptSubmit", prompt=prompt)
            self.assertEqual(again, {})
        finally:
            os.environ.pop("TOKEN_STEWARD_CONFIG", None)

    def test_dedupes_streamed_lines_and_does_not_double_count(self):
        s = Session()
        s.hook("UserPromptSubmit", prompt="summarize these notes for the partner")
        s.respond("claude-sonnet-5-5", inp=1000, out=500, cr=0, chunks=4)
        s.hook("Stop", effort={"level": "medium"})
        s.hook("Stop", effort={"level": "medium"})  # e.g. a second Stop with no new responses
        rows = s.ledger()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tokens"]["output"], 500)
        self.assertAlmostEqual(rows[0]["cost"], (1000 * 2 + 500 * 10) / 1e6, places=6)

    def test_fails_open_on_garbage(self):
        s = Session()
        res = subprocess.run([sys.executable, str(CLI), "hook", "stop"], input="not json",
                             capture_output=True, text=True, env={**s.env(), "TOKEN_STEWARD_DEBUG": ""})
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, "")

    def test_no_prompt_text_persisted(self):
        s = Session()
        secret = "Project Falcon acquisition target Contoso"
        s.turn(f"Rephrase: {secret}", "claude-opus-5-5", "high")
        for f in s.data.rglob("*"):
            if f.is_file():
                self.assertNotIn("Falcon", f.read_text())


if __name__ == "__main__":
    unittest.main()
