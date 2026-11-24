# How Token Steward measures usage, limits and savings

By default (`"framing": "usage"`) Token Steward talks about tokens and plan limits, not money. That matches how most people pay: on Pro, Max, Team and seat-based Enterprise plans, a lighter model doesn't change the bill, it makes the session and weekly limits go further. Firms billed per token can set `"framing": "dollars"` to see the cost figures described in sections 1 to 5.

## Usage framing at a glance

| Figure | Source | Measured or estimated |
|---|---|---|
| Tokens per task | `usage` on each assistant response in the session transcript: input, output (including reasoning), cache writes and cache reads | Measured |
| Session and weekly limit used, and reset times | Claude Code's `rate_limits` (`five_hour`, `seven_day`), which it passes only to the status line, for Pro, Max and Ultra plans. `/token-steward:setup-statusline` saves each update to `~/.claude/token-steward/limits.json`; tips use it while it is under 12 hours old and its window hasn't reset | Measured |
| "About N× less of your usage limit" | The ratio of the same tokens priced on the two setups (section 2). Anthropic says model and effort affect how fast limits are used but publishes no weights, so relative price is the proxy | Estimated, and labelled so |
| Right-sized task | A task that ran lighter than the reference setup | Measured against the reference |

Each ledger row also records the limit percentages at the time, so a firm can later check the price-based estimate against how limits actually moved.

# Dollar framing

Anyone quoting the savings figure should be able to defend it. This page explains how each number is produced and where the estimates are.

## 1. Actual cost (measured)

When a turn completes, the `Stop` hook reads the session transcript from the point the prompt was submitted. Each assistant API response there carries:

| Transcript field | Priced at |
|---|---|
| `usage.input_tokens` | model input rate |
| `usage.output_tokens` (includes reasoning/thinking) | model output rate |
| `usage.cache_creation_input_tokens` | cache-write rate (1.25× input) |
| `usage.cache_read_input_tokens` | cache-read rate |

A single response is often written as several transcript lines that repeat the same usage, so responses are de-duplicated by message id. A turn that uses several models (for example a mid-turn fallback) is priced per model. Models not in the pricing table are skipped, not guessed.

Prices are Anthropic first-party list prices per million tokens, in `config/defaults.json`. If your firm buys through Amazon Bedrock, Google Vertex AI, or an enterprise agreement, put your own rates in the org override file.

## 2. Reference cost (counterfactual)

The saving is `reference cost − actual cost`, where the reference is a fixed configuration the firm chooses (default **Opus 5.5 @ high**). It answers one question: *"What would this exact piece of work have cost on the premium setup?"*

- **Input-side tokens are held constant.** The same conversation would have been sent either way.
- **Output tokens are scaled for effort.** Effort mainly changes how much the model reasons and writes. Output is multiplied by `effort_output_multiplier[reference] / effort_output_multiplier[actual]` and priced at the reference model's output rate.

Default multipliers (medium = 1.0): low 0.6 · medium 1.0 · high 1.5 · xhigh 2.0 · max 2.8.

These multipliers are **planning assumptions**, deliberately conservative, and the only modelled part of the calculation. `/token-steward:calibration` shows the median output tokens per task at each effort level from your own history. Those observed ratios mix effort with task difficulty (people choose high effort for harder work), so treat them as an upper bound when tuning.

The model-switch component involves no modelling: it's the same token counts at a different price. For a typical light task moved from Opus to Sonnet, most of the saving comes from that part.

## 3. What is never claimed

- **No negative savings in totals.** A turn that ran *above* the reference (for example Fable @ max) is recorded with its real cost and a negative `savings` value in the ledger, but it doesn't reduce anyone's displayed savings and is never shown as a reprimand.
- **No savings at the reference.** A task run on the reference configuration saves exactly zero.
- **No savings from tips alone.** A tip counts as *acted on* only when a later turn actually ran on a lower model tier or effort than the one flagged.

## 4. Known biases

| Bias | Direction | Mitigation |
|---|---|---|
| A lighter model might need an extra round to finish the job | Overstates savings | The extra round is itself measured and priced, so it's included in *actual cost* |
| Effort multipliers are assumptions | Either direction | Conservative defaults; calibration view; firm-tunable |
| Tokenizer differences between model generations | Small | None. Current-generation models share a tokenizer |
| "Would they really have used the reference?" | Overstates savings for people who always use light models | Set the reference to the firm's real default; `include_user_id` telemetry lets you compare against each person's own history |

## 5. Estimated savings in tips

The figure in a tip ("≈ $0.15 per request like this") is a forecast, not a measurement. It uses the median token profile of your last 50 completed tasks of the same class, or the configured `default_turn_tokens` until you have 5, priced on the current and suggested setups.
