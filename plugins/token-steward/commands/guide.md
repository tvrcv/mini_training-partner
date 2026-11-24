---
description: The right-sizing playbook - which model and effort for which kind of work
model: haiku
---
Show the user the playbook below exactly as written, as Markdown, with no additions.

## Right-sizing playbook

**The rule of thumb:** start light, escalate when the work proves it needs more. Moving up takes one command; paying for headroom you never use adds up across a whole firm.

| Kind of work | Model | Effort | Switch with |
|---|---|---|---|
| Rewording, proofreading, formatting, translation, short emails, quick lookups, Excel formulas, renames and other one-line code chores | Haiku | low | `/model haiku` · `/effort low` |
| Summarising notes or documents, drafting slides and memos, everyday coding, writing tests, routine analysis | Sonnet | medium | `/model sonnet` · `/effort medium` |
| Multi-step problems: system design, hard debugging, large refactors, synthesis across many sources, modelling with real trade-offs | Opus | high | `/model opus` · `/effort high` |
| The hardest, highest-stakes reasoning, where a wrong answer is expensive | Fable | high, `xhigh` only if it measurably helps | `/model fable` |

**Habits that save the most**

1. **Effort is the cheapest lever.** Lower effort means less hidden reasoning, and reasoning is billed as output, the most expensive kind of token. Try `medium` before `high`, `high` before `max`.
2. **Don't leave `max` or `ultrathink` on.** Use them for one hard question, then step back down.
3. **Start fresh for a new topic** (`/clear`). Long conversations re-send all of their history with every message.
4. **Give a complete brief up front.** One clear request costs less than five rounds of clarification.
5. **Escalate on evidence.** If a lighter setup gets it wrong, move up; that is a good use of the bigger model.

Token Steward will occasionally suggest a lighter setup when a request looks simple. It never blocks you and it will be wrong sometimes. You're the judge. `/token-steward:savings` shows what your choices have saved; `/token-steward:snooze` pauses tips.
