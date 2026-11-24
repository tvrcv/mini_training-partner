# Rolling out Token Steward firm-wide

Audience: IT, AI enablement, and whoever owns the AI budget.

## 1. Host the marketplace

This repository is a Claude Code plugin marketplace. Host it (or a fork) somewhere your people's machines can reach: an internal GitHub org works well. Fork it if you want to change defaults in `plugins/token-steward/config/defaults.json` rather than ship an override file.

## 2. Enable it for everyone with managed settings

Add the marketplace and enable the plugin in your managed settings, through server-managed settings in the claude.ai admin console, MDM, or a `managed-settings.json` file. A starting point is in [`examples/managed-settings.json`](../examples/managed-settings.json):

```json
{
  "extraKnownMarketplaces": {
    "ai-stewardship": {
      "source": { "source": "github", "repo": "YOUR-ORG/mini_training-partner" }
    }
  },
  "enabledPlugins": {
    "token-steward@ai-stewardship": true
  },
  "env": {
    "TOKEN_STEWARD_BASELINE_MODEL": "claude-opus-5-5",
    "TOKEN_STEWARD_BASELINE_EFFORT": "high"
  }
}
```

Check the current managed-settings docs for your Claude Code version before deploying. Run `/status` on a test machine to confirm the managed source loaded, and `/plugin` to confirm the plugin is enabled.

Server-managed settings are the only kind that also reach cloud sessions (claude.ai/code).

## 3. Choose your policy

Every key in `config/defaults.json` can be overridden. Point `TOKEN_STEWARD_CONFIG` at a JSON file containing only the keys you want to change; it's deep-merged over the defaults. See [`examples/org-policy.json`](../examples/org-policy.json).

| Decision | Key | Default | Notes |
|---|---|---|---|
| Tokens and limits, or dollars | `framing` | `usage` | `usage` for Pro, Max, Team and seat-based Enterprise; `dollars` only if you pay per token (API keys, usage-based billing, Bedrock, Vertex). The extension's equivalent is `costFraming` (`allowance` or `dollars`) |
| What savings are measured against | `baseline.model`, `baseline.effort` | Opus 5.5 @ high | Set this to the setup people actually default to today, or the numbers will be inflated |
| Prices | `pricing` | Anthropic list prices | Use your contracted or Bedrock/Vertex rates |
| How assertive tips are | `nudge.mode` | `advise` | `confirm` holds a prompt once, only for severe mismatches (severity ≥ `confirm_min_severity`, e.g. a trivial edit at max effort on the top model). Pressing Enter again on the same prompt sends it unchanged |
| How often tips appear | `nudge.min_prompts_between_nudges`, `min_minutes_between_nudges`, `max_nudges_per_session`, `stop_after_consecutive_ignored` | 3 / 10 / 4 / 3 | Err toward fewer. A tip people learn to ignore teaches nothing |
| Ask the model to be brief on trivial tasks | `nudge.concise_hint_for_trivial` | off | Adds one sentence to Claude's context. Saves output tokens but changes behaviour silently, so it's off unless you choose it |
| Upgrade tips | `upgrade.enabled`, `upgrade.target`, `upgrade.max_per_session` | on, Opus @ high, 2 per session | Suggest moving up when complex work runs on a light setup |
| Celebrations | `celebrations.enabled`, `celebrations.milestones_right_sized_tasks`, `celebrations.milestones_usd` | on; 10, 25, 50 … right-sized tasks | Usage framing celebrates right-sized task counts; dollar framing celebrates `milestones_usd` |
| Firm vocabulary | `classifier.signals` | Consulting + engineering terms | Add your own deliverable names (e.g. "steerco deck", "IC memo") with the weight you want. After any change, add examples to `tests/fixtures/prompts.json` and run the tests: they fail if real work starts being called light |

**Not recommended:** making `confirm` the default for everyone, or shortening the cooldowns. Our working assumption is that a guardrail that slows people down loses their trust and gets uninstalled.

## Status line for limit figures

Plan limits reach Claude Code's status line and nothing else. Ask people to run `/token-steward:setup-statusline` once: it copies a small script to `~/.claude/token-steward/` and adds a `statusLine` to their user settings, unless they already have one (then it explains how to combine them). To roll it out centrally, set the same `statusLine` in managed settings, pointing at a copy of `plugins/token-steward/scripts/statusline.py` you install on each machine.

## 4. Optional hard limits (outside this plugin)

Token Steward is about awareness. If you also want hard limits, Claude Code has managed settings for them:

- `maxEffortLevel` caps the reasoning effort anyone can select.
- `availableModels` restricts which models can be chosen.

Use them sparingly. A cap stops the 2% of work that really needs `max`, and people route around rules they find arbitrary.

## 5. Measuring firm-wide impact

Each user's numbers live in their own plugin data directory (`~/.claude/plugins/data/token-steward-…/`): `ledger.jsonl` (one anonymous row per task) and `totals.json`.

To aggregate, pick one:

1. **Telemetry endpoint (simplest).** Set `telemetry.endpoint` to an HTTPS endpoint you control. Each completed task POSTs one JSON record: model, effort, task class, token counts, cost, reference cost, savings, and whether a tip was shown or acted on. The session id is hashed. Leave `include_user_id` off unless you have a reason and your works council or privacy office agrees. **No prompt or response text is ever included.**
2. **Periodic export.** Ask teams to run `/token-steward:export` and share the CSV.
3. **Claude Code's own OpenTelemetry.** Claude Code can export cost and token metrics via OpenTelemetry. That gives you spend by model; Token Steward adds why (task class) and what changed (tips acted on, savings).

Metrics worth reporting monthly:

- **Share of light tasks run on Opus/Fable**: the core behaviour you want to move.
- **Tip acted-on rate**: whether the tips are landing. Below ~10% after a month, revisit wording or thresholds.
- **Reported savings vs. invoice trend**: a sanity check on the methodology.
- **Spend per task by team**: compare on a per-task basis rather than total spend. Heavy users of AI are not the problem.

## 6. Communications

Launch it as a cost-awareness tool, not surveillance:

- Say what is and isn't collected (section 5).
- Lead with the playbook (`/token-steward:guide`). Most people simply don't know which settings matter.
- Celebrate savings publicly. Avoid naming high spenders: expensive tasks are often the right call.

## 7. Platform notes

- Requires `python3` on `PATH`. On Windows machines without it, either install Python or change the three commands in `hooks/hooks.json` to `py -3 …` in your fork.
- Hooks run in the Claude Code CLI, the desktop app's Code tab and the IDE extensions.
- A hook that errors or times out is skipped and the session continues normally.
