---
name: guide
description: Right-sizing playbook for choosing a Claude model (Haiku, Sonnet, Opus, Fable) and reasoning effort (low to max, extended thinking) for a task. Use when the user asks which model or effort to use, whether a setup is overkill, how to save tokens, cost or usage allowance, why they hit a usage limit, or invokes the Token Steward guide.
---

# Right-sizing playbook

Help the person pick the lightest setup that will do the job well. Be brief and practical, never preachy, and leave the decision to them.

## How to respond

- **Asked for the playbook or guide:** show the table and habits below as written.
- **Asked about a specific task** ("which model for this?", "is Opus overkill for X?"): give one recommendation (model and effort) with a one-sentence reason drawn from the table, plus how to switch. If the task is genuinely hard, say so plainly and recommend the bigger setup. Right-sizing goes both ways.
- **Asked about cost or limits:** explain that heavier models and higher effort use more tokens per message (reasoning is billed as output, the most expensive kind), and that long conversations re-send their whole history every turn. On seat-based plans this shows up as reaching usage limits sooner; on usage-based plans, as cost. Don't quote dollar figures you can't see.
- **Don't** lecture about choices nobody asked about, and don't refuse or water down an answer because of the setup in use.

## How to switch

- **Claude Code and Cowork:** `/model haiku|sonnet|opus|fable` and `/effort low|medium|high|xhigh|max`.
- **claude.ai chat:** the model menu next to the message box, and the extended thinking or effort control in the same area. Changes apply from the next message.

## Playbook

**The rule of thumb:** start light, and escalate when the work proves it needs more. Moving up takes one click; paying for headroom you never use adds up across a whole firm.

| Kind of work | Model | Effort |
|---|---|---|
| Rewording, proofreading, formatting, translation, short emails, quick lookups, Excel formulas, renames and other one-line code chores | Haiku | low, thinking off |
| Summarising notes or documents, drafting slides and memos, everyday coding, writing tests, routine analysis | Sonnet | medium |
| Multi-step problems: system design, hard debugging, large refactors, synthesis across many sources, modelling with real trade-offs | Opus | high |
| The hardest, highest-stakes reasoning, where a wrong answer is expensive | Fable | high; xhigh only if it measurably helps |

**Habits that save the most**

1. **Effort is the cheapest lever.** Lower effort means less hidden reasoning. Try medium before high, and high before max.
2. **Don't leave max effort, extended thinking or `ultrathink` on.** Use them for one hard question, then step back down.
3. **Start a new chat for a new topic** (`/clear` in Claude Code). Long conversations re-send all of their history with every message.
4. **Give a complete brief up front.** One clear request costs less than five rounds of clarification.
5. **Escalate on evidence.** If a lighter setup gets it wrong, move up; that is a good use of the bigger model.

In Claude Code and Cowork, Token Steward occasionally suggests a lighter setup when a request looks simple. It never blocks you and will sometimes be wrong; you're the judge. `/token-steward:savings` shows what your choices have saved, and `/token-steward:snooze` pauses tips.
