# Token Steward use-case playbook

_Repository copy of the shared playbook doc, as of 24 November 2026. Keep the two in step when either changes._

Use the lightest setup that does the job well: Haiku for edits and lookups, Sonnet for everyday drafting and analysis, Opus for multi-step problems, and Fable only for the hardest, highest-stakes reasoning. On a typical routine request, Sonnet at medium effort uses roughly half as much of your usage limit as Opus at high, and Haiku about a fiftieth (estimates).

## Decide in ten seconds

Ask these in order and stop at the first yes:

1. **Could a sharp analyst do it in under five minutes without thinking hard?** Rewording, formatting, translating, a formula, a definition. Use **Haiku**, extended thinking off.
2. **Is the answer mostly in what you're giving it?** Summarising a transcript, drafting from your notes, cleaning a dataset, everyday code. Use **Sonnet** at medium effort.
3. **Does it need judgement across many moving parts?** An issue tree, a model's logic, synthesis across many sources, a recommendation with real trade-offs. Use **Opus** at high effort.
4. **Would a wrong answer be costly and hard to catch, even after Opus?** Use **Fable** at high effort, for that question only.

Not sure? Start one level lower than your instinct. If the answer falls short, move up and re-ask. That uses far less of your limit than defaulting to the top every time.

## What each choice uses

A light request on Opus at high effort uses roughly 65 times as much of your usage limit as the same request on Haiku, and Fable at max about 200 times. Estimated share of your limit for one request, relative to Haiku:

| Request | Tokens, roughly | Fable at max effort | Opus at high effort | Sonnet at medium effort | Haiku, thinking off |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reword a client email | 5k | 200× | 65× | 25× | 1× |
| Summarise a one-hour interview transcript | 20k | 150× | 55× | 25× | 1× |
| Synthesise findings across 20 documents | 130k | 130× | 50× | 20× | 1× |

One request barely moves the needle. The habit is what uses up a week's limit:

- **Conversations multiply it.** Every follow-up re-sends the whole conversation, so ten exchanges in one long chat can use five to ten times the tokens of one fresh request.
- **Agents multiply it again.** In Claude Code or Cowork, one task can run 20 or more model calls.
- **Effort multiplies it too.** Higher effort means more hidden reasoning, which is billed as output tokens.

To see where you stand, run `/token-steward:setup-statusline` once in Claude Code: your session and weekly limit usage then shows under the message box, and Token Steward's tips quote it.

If the firm pays per token rather than per seat, the same choices are money: as an illustration, moving 40% of 4.4 million yearly requests from Opus to Haiku and 30% to Sonnet is about $170,000 a year at list prices for 1,000 consultants.

## Use cases by workflow

Most day-to-day consulting work belongs on Haiku or Sonnet. The right-hand column says when to move up.

| Workflow | Example request | Setup | Move up when |
| --- | --- | --- | --- |
| Client communication | "Make this email to the client more formal and cut it to five lines" | Haiku | The message is sensitive: a scope change, a fee discussion, bad news (Sonnet) |
| Client communication | "Draft a status update for the steerco from these bullet notes" | Sonnet | You need it to argue a position the notes don't already make (Opus) |
| Slides and documents | "Give me five sharper action titles for this slide" | Haiku | Titles have to carry a storyline across the whole deck (Sonnet) |
| Slides and documents | "Turn these findings into a ten-slide storyline with one message per slide" | Sonnet | The findings conflict and need a recommendation (Opus) |
| Slides and documents | "Proofread this executive summary" or "Translate this page into German" | Haiku | Never for proofreading; for translation, legal or contractual text (Sonnet) |
| Research and synthesis | "Summarise this expert call transcript into key takeaways and quotes" | Sonnet | You need patterns across ten or more calls (Opus) |
| Research and synthesis | "What is net revenue retention and how is it calculated?" | Haiku | You need it applied to the client's numbers (Sonnet) |
| Research and synthesis | "Synthesise these 20 analyst reports into a view on market growth, flagging where they disagree" | Opus | The conclusion feeds an investment decision (Fable, for the final check) |
| Data and Excel | "Write an XLOOKUP that pulls revenue from the Data tab by client ID" | Haiku | The workbook logic itself is broken and needs diagnosing (Sonnet) |
| Data and Excel | "Write a pandas script to clean this survey export and tabulate results by segment" | Sonnet | The analysis design is open: weighting, significance, segmentation (Opus) |
| Modelling and analysis | "Build a market sizing for EU cold-chain logistics with three scenarios" | Opus | The model will be used in a client deliverable without expert review (Fable, for the review) |
| Modelling and analysis | "Check this DCF for logic errors and walk me through the sensitivities" | Opus | Rarely. Ask a human reviewer before you move to Fable |
| Problem structuring | "Build an issue tree for why the client's margins fell 4 points" | Opus | Rarely needed |
| Problem structuring | "Reformat this issue tree as a table" | Haiku | Never |
| Meetings and admin | "Turn these meeting notes into action items with owners and dates" | Haiku | Notes are long and messy, or decisions need interpreting (Sonnet) |
| Code and automation | "Fix the typo in this function name" or "Write a regex for UK postcodes" | Haiku | It fails on real data (Sonnet) |
| Code and automation | "Add tests for this module" or "Write a script to rename these files from the index" | Sonnet | The bug is intermittent or spans many files (Opus) |
| Code and automation | "Design the data pipeline for the client dashboard" | Opus | Rarely needed |

## When to go big

Opus at high effort is the right call when the work has many moving parts and a weak answer would cost more than the tokens. That includes:

- Structuring a new problem: issue trees, hypotheses, a workplan for a new engagement.
- Analysis with real trade-offs: pricing strategy, make-or-buy, a market entry decision.
- Synthesis across many sources where they disagree: diligence data rooms, ten or more expert calls, conflicting reports.
- Checking the logic of a model or an analysis before it goes to a client.
- Hard technical work: an intermittent bug, a data architecture, a migration.

Fable is for the narrow set where a wrong answer is expensive and hard to catch: a final check of an investment recommendation, a red-team of a board-level conclusion, a novel quantitative problem. Use it for that question, then step back down.

Moving up after a lighter setup falls short is good practice, not waste. Token Steward will also suggest moving up when a request looks complex and you're on a light setup.

## Habits that cut cost without changing model

| Habit | Instead of | Try |
| --- | --- | --- |
| Give the whole brief at once | Five rounds of "also make it shorter", "now add the numbers", "use our template" | One request: "Draft a five-line update for the CFO, include Q3 revenue and the two risks, in our steerco format" |
| Start a new chat for a new topic | Asking about a new deck in the same chat you used for last week's model | A fresh chat. Long chats re-send everything with every message |
| Ask for the length you need | "Tell me about the client's competitors" | "List the client's five largest competitors with one line each on positioning" |
| Give only the relevant material | Pasting a 60-page report to ask about one table | Paste the table, or name the section |
| Lower effort before changing model | Opus at max effort for a routine summary | The same model at medium effort, or Sonnet |
| Turn deep thinking off after use | Leaving max effort, extended thinking or "ultrathink" on all afternoon | Use it for the one hard question, then switch back |

## Costly patterns to avoid

| Pattern | Why it's costly | Do instead |
| --- | --- | --- |
| Top model as the default for everything | Burns through the weekly limit on requests that don't need it | Default to Sonnet; move up per task |
| One chat for the whole week | Every message re-sends days of history | New chat per topic or deliverable |
| "Make it better" loops | Each round re-sends the draft and buys a full rewrite | Say what's wrong: "cut to 100 words, lead with the ask" |
| Proofreading on Opus at high effort | Deep reasoning spent on commas | Haiku, thinking off |
| Pasting whole documents for one fact | Pays to read pages it doesn't need | Paste the relevant section |
| Agents on maximum effort for simple chores | Every step of the agent runs at maximum | `/effort medium` for routine agent work |

## For team leads

Coach the habit, not the spend. Heavy AI users are often your most productive people.

- **Model it.** Say out loud which setup you're using and why, especially when you move up for a hard problem.
- **Share the playbook at kickoff.** Add a line on model choice to your engagement norms, next to file naming and review cycles.
- **Look at the mix, not the total.** `/token-steward:savings` and the browser dashboard show which setups each person uses. A team running most light work on Haiku and Sonnet is doing it right, whatever its total.
- **Celebrate the milestones.** Token Steward celebrates each person's right-sized task milestones (10, 25, 50 and up). Mention them in team meetings.
- **Tell us when a tip is wrong.** Wrong tips cost trust. Send examples to [contact or channel] so we can tune the rules for your practice's work.

## Assumptions behind the numbers

- Anthropic doesn't publish how fast each model uses up a limit, so relative usage is estimated from its list prices per million tokens as of November 2026: Fable 5.2 $8 in / $40 out, Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 5.5 $0.10 / $0.50. Contracted or cloud-marketplace rates may differ.
- Example requests assume 4,000 tokens in and 800 out for an email, 18,000 in and 2,000 out for a transcript summary, and 120,000 in and 8,000 out for a 20-document synthesis, all at medium effort.
- Reasoning effort is modelled as output volume relative to medium: low 0.6×, high 1.5×, max 2.8×. These are planning assumptions, not measurements.
- Token counts and limit percentages in Token Steward's messages are measured; the comparisons between setups are estimates. The firm-wide dollar figure is an illustration, not a forecast.
