# Token Steward

**A Claude Code plugin that helps people match the model and reasoning effort to the task, and shows what that saves.**

Teams that adopt AI tools quickly tend to settle on the most powerful model at the highest reasoning effort, whatever the task. Rewording an email on a frontier model at maximum effort costs many times more than the same edit on a lighter setup, and usually turns out no better. Across a firm, that becomes a real line item and a habit that's hard to see.

Token Steward makes that cost visible at the moment it matters. It never blocks or slows anyone down.

```
Token Steward · This looks like a quick, lightweight request (rewrite / polish, email / message draft).
You're on Opus 5.5 at high effort, which is built for complex, multi-step work. Haiku 5.5 at low effort
typically handles requests like this just as well, at about 98% lower cost (≈$0.15 per request like this).
To switch for what follows: /model haiku then /effort low. Your request is running as-is.
```

```
Token Steward · Thanks for switching, and for considering your usage. This task ran on Haiku 5.5 @ low
for <$0.01, about $0.15 less than Opus 5.5 @ high. You've saved the business $1.85 this session,
$12.40 this month and $48.10 in total.
```

## What it does

| When | What the user sees | Why |
|---|---|---|
| Session start (once a day) | A one-line reminder of the playbook: Haiku for quick edits, Sonnet for everyday work, Opus/Fable for hard problems | Sets the norm without lecturing |
| A light request runs on a heavy setup | A short tip naming the current setup, a right-sized alternative, the estimated saving, and the exact command to switch | Feedback at the moment of decision is what changes habits |
| A task finishes on a lighter setup than the reference | A thank-you with that task's saving and running totals for the session, month and all time | Positive reinforcement, and a number people can quote |
| `/token-steward:savings` | Personal dashboard: spend, counterfactual cost, savings, model mix, tips acted on | Self-awareness without a manager in the loop |
| `/token-steward:guide` | The right-sizing playbook (a skill, so it also works in claude.ai chat) | One page anyone can follow |
| `/token-steward:snooze [hours\|off]` | Pauses tips (default 4 hours) | Respects focus; usage is still measured |
| `/token-steward:export` | CSV of your usage ledger | For your own analysis or a firm-wide roll-up |

For **claude.ai chat**, the [browser extension](extension/README.md) shows the same kind of tip while you type, before you send, and a thank-you with estimated savings after the reply.

## Design principles

The design follows from how we'd want a guardrail to behave for our own engineers:

1. **Never slow anyone down.** The prompt-time check is a local heuristic (~75 ms, no network, no model call). In the default `advise` mode nothing is ever blocked, and every hook fails open: if anything goes wrong, the session carries on as if the plugin weren't there.
2. **Inform, don't police.** Tips say what's running, what would likely suffice, and what that's worth, then defer to the person: *"Your request is running as-is."* People respond better to being trusted than to being blocked.
3. **Stay quiet unless the evidence is clear.** A task is only called light when explicit light-work signals match (rewrite, format, translate, summarise and so on). Ambiguous or complex requests are never flagged. Cooldowns, a per-session cap and automatic back-off after three ignored tips keep it from turning into noise people learn to ignore.
4. **Be honest about the numbers.** Every saving names the configuration it's compared with. Costs come from real token counts in the session transcript and list prices; only the effort component is modelled, and those assumptions are documented and tunable ([METHODOLOGY](docs/METHODOLOGY.md)). Nothing is claimed for tasks that ran at or above the reference.
5. **Private by default.** Prompt and response text is never stored or sent. The local ledger holds token counts, model, effort, cost and a task class. Org telemetry is off unless an admin turns it on, and even then carries only those anonymous metrics.

## How it works

```
UserPromptSubmit ──► classify the prompt (local regex heuristic)
                     detect model + effort (transcript, settings, env)
                     mismatch? ──► tip (systemMessage), rate-limited
Stop             ──► read this turn's token usage from the transcript
                     cost on the actual model  vs.  the same work on the reference config
                     append to local ledger; thank the user if they saved
SessionStart     ──► daily one-line playbook reminder
```

Severity is `2 × (model tier gap) + (effort level gap)` against the recommendation for the task class. Tips fire at severity ≥ 2. For example: a routine task on Opus fires; a routine task on Sonnet at `high` doesn't.

## Install

**For yourself** (inside Claude Code):

```
/plugin marketplace add <your-org>/mini_training-partner
/plugin install token-steward@ai-stewardship
```

**Firm-wide:** see [docs/ADMIN.md](docs/ADMIN.md) for Claude Code, and [docs/CLAUDE-AI.md](docs/CLAUDE-AI.md) for distributing through claude.ai organization settings to Cowork and chat. In short, push the marketplace and an enabled plugin through managed settings, then optionally set your own reference configuration, pricing and telemetry.

Requires Python 3.8+ on `PATH` as `python3`. No third-party packages.

## Repository layout

```
.claude-plugin/marketplace.json        marketplace (this repo is installable as-is)
plugins/token-steward/
  .claude-plugin/plugin.json
  hooks/hooks.json                     SessionStart, UserPromptSubmit, Stop
  commands/                            savings, snooze, export
  skills/guide/                        right-sizing playbook (loads in Claude Code, Cowork and chat)
  config/defaults.json                 pricing, policy, classifier signals (all tunable)
  scripts/token_steward.py             entry point
  scripts/steward/                     classifier, detection, pricing, transcript, ledger, reports
docs/ADMIN.md                          rollout guide for IT / AI enablement
docs/METHODOLOGY.md                    exactly how costs and savings are computed
docs/CLAUDE-AI.md                      Cowork and claude.ai chat
extension/                             Chrome/Edge extension: tips and savings in claude.ai chat
tools/build_extension_config.py        copies pricing/policy/classifier into the extension
examples/                              managed-settings and org-policy templates
tests/                                 end-to-end hook tests
```

## Development

```bash
python3 -m unittest discover -s tests -v          # plugin
node --test tests/extension/core.test.js          # extension logic (+ parity with the plugin classifier)
node --test tests/extension/e2e.test.js           # extension in real Chromium (needs Playwright)
```

After changing `plugins/token-steward/config/defaults.json`, run `python3 tools/build_extension_config.py` so the extension uses the same pricing and rules.

Set `TOKEN_STEWARD_DEBUG=1` to see hook errors on stderr.

## Scope and limits

- Tips and savings need plugin hooks, which run in Claude Code and Cowork. claude.ai chat ignores hooks: there the plugin provides the guide skill, and the optional browser extension provides tips. See [docs/CLAUDE-AI.md](docs/CLAUDE-AI.md).
- The tip fires *as* a prompt is submitted, so it shapes the **next** request rather than the current one. That's deliberate: holding a prompt would slow people down. Admins who want a stronger nudge for egregious cases can enable `confirm` mode (see ADMIN).
- Subagent token usage is recorded in separate transcripts and isn't yet counted.
- The classifier is a heuristic. It will sometimes miss light work, and occasionally flag something that deserved the bigger model. Tune `classifier.signals` for your firm's vocabulary.
