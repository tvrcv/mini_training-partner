# Token Steward

**A Claude Code plugin that helps people match the model and reasoning effort to the task, so their tokens and plan limits go further.**

Teams that adopt AI tools quickly tend to settle on the most powerful model at the highest reasoning effort, whatever the task. Rewording an email on a frontier model at maximum effort uses many times the tokens and limit of the same edit on a lighter setup, and usually turns out no better. People then hit their session and weekly limits early, or, on per-token billing, run up a real bill.

Token Steward makes that visible at the moment it matters. It never blocks or slows anyone down.

```
Token Steward · This looks like a quick, lightweight request (rewrite / polish, email / message draft).
You're on Opus 5.5 at high effort, which is built for complex, multi-step work. Haiku 5.5 at low effort
typically handles requests like this just as well, and uses about 50× less of your usage limit (estimate).
To switch for what follows: /model haiku then /effort low. You've used 41% of this week's limit
(resets Fri 22:38) and 23% of this session's. Your request is running as-is.
```

```
Token Steward · 🎉 Your first tip acted on. Thank you! This task used 33k tokens on Haiku 5.5 @ low, about
60× less of your usage limit than Opus 5.5 @ high would take (estimate). Right-sized tasks in the last
7 days: 1. You've used 41% of this week's limit (resets Fri 22:38) and 23% of this session's.
```

Token counts and limit percentages are measured; "× less of your usage limit" is an estimate, and says so. Firms that pay per token can switch every message to dollars instead (`"framing": "dollars"`).

## What it does

| When | What the user sees | Why |
|---|---|---|
| Session start (once a day) | A one-line reminder of the playbook, plus last week's tokens, right-sized tasks and limit usage | Sets the norm without lecturing |
| A light request runs on a heavy setup | A short tip naming the current setup, a right-sized alternative, roughly how much less of the limit it uses, where the week's limit stands, and how to switch | Feedback at the moment of decision is what changes habits |
| Complex work runs on a light setup | A tip suggesting the stronger setup, because a right first answer costs less than several retries | Right-sizing goes both ways; it shows people the tool is on their side |
| A task finishes on a lighter setup than the reference | A thank-you with the task's tokens, how much lighter it was, right-sized tasks this week, and limit usage | Positive reinforcement, in numbers people recognise |
| A milestone (10, 25, 50 … right-sized tasks), or the first tip acted on | A celebration: confetti in the browser, a celebratory message in Claude Code | Makes the habit visible and worth repeating |
| `/token-steward:setup-statusline` | Your model plus session and weekly limit usage under the message box, and those numbers in every tip | The only place Claude Code exposes plan limits; one command turns it on |
| `/token-steward:savings` | Dashboard: tasks, right-sized tasks, tokens, how much lighter than the reference, model mix, tips acted on | Self-awareness without a manager in the loop |
| `/token-steward:guide` | The right-sizing playbook (a skill, so it also works in claude.ai chat) | One page anyone can follow |
| `/token-steward:snooze` · `/token-steward:resume` | Pauses tips for 4 hours, or turns them back on | Respects focus; usage is still measured |
| `/token-steward:export` | CSV of your usage ledger | For your own analysis or a firm-wide roll-up |

For **claude.ai chat**, the [browser extension](extension/README.md) shows the same kind of tip while you type, before you send, and a thank-you after the reply with estimated tokens.

## Design principles

The design follows from how we'd want a guardrail to behave for our own engineers:

1. **Never slow anyone down.** The prompt-time check is a local heuristic (~75 ms, no network, no model call). In the default `advise` mode nothing is ever blocked, and every hook fails open: if anything goes wrong, the session carries on as if the plugin weren't there.
2. **Inform, don't police.** Tips say what's running, what would likely suffice, and how much of the limit that spares, then defer to the person: *"Your request is running as-is."* People respond better to being trusted than to being blocked.
3. **Measured, not assumed.** `tests/fixtures/prompts.json` holds labelled consulting and engineering prompts. Tests require that heavy and ambiguous work is never called light, that at least 90% of light work is recognised, and that at least 85% of complex work is recognised. The extension must classify every prompt in the set exactly as the plugin does. Add your firm's own (anonymised) prompts to tighten it.
4. **Stay quiet unless the evidence is clear.** A task is only called light when explicit light-work signals match (rewrite, format, translate, summarise and so on). Ambiguous or complex requests are never flagged. Cooldowns, a per-session cap and automatic back-off after three ignored tips keep it from turning into noise people learn to ignore.
5. **Be honest about the numbers.** Token counts come from the session transcript, and session and weekly limit percentages come from Claude Code itself (via the status line). How much more of a limit one setup uses than another is an estimate based on relative model price, because Anthropic doesn't publish per-model limit weights; every such figure says "estimate". Every comparison names the reference setup, and nothing is claimed for tasks that ran at or above it ([METHODOLOGY](docs/METHODOLOGY.md)).
6. **Private by default.** Prompt and response text is never stored or sent. The local ledger holds token counts, model, effort, cost and a task class. Org telemetry is off unless an admin turns it on, and even then carries only those anonymous metrics.

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

**In this repository:** `.claude/settings.json` declares the marketplace and enables the plugin, so Claude Code offers to install Token Steward when you open the repository (after you trust the folder), and new cloud sessions on it can pick it up.

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
docs/PLAYBOOK.md                       use cases and examples for consultants (also kept as a shared doc)
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
