"""Personal savings report, calibration view and CSV export (used by the slash commands)."""

import csv
import io
import statistics
import time
from collections import defaultdict

from . import pricing, store
from . import usage as plan_usage


def _bucket(rows):
    out = {"turns": len(rows), "cost": 0.0, "baseline": 0.0, "savings": 0.0}
    for r in rows:
        out["cost"] += r["cost"]
        out["baseline"] += r["baseline_cost"]
        out["savings"] += max(r["savings"], 0.0)
    return out


def _usage_report(cfg, rows, totals, base_label):
    now = time.time()
    periods = [
        ("Last 24 hours", [r for r in rows if now - r["ts"] < 86400]),
        ("Last 7 days", [r for r in rows if now - r["ts"] < 7 * 86400]),
        ("This month", [r for r in rows if store.month_key(r["ts"]) == store.month_key(now)]),
        ("All time", rows),
    ]
    lines = ["# Your AI usage", ""]
    limits = plan_usage.limits_sentence()
    lines.append(limits if limits else
                 "Session and weekly limit figures appear here once the Token Steward status line is on "
                 "(run /token-steward:setup-statusline, Pro, Max and Ultra plans).")
    lines += ["", f"\"Lighter\" compares each task with **{base_label}**, the firm's reference setup. "
              "It is an estimate: Anthropic doesn't publish how fast each model uses up a limit, so "
              "relative model price stands in for it.", "",
              "| Period | Tasks | Right-sized | Tokens | Usage vs reference |",
              "|---|---:|---:|---:|---:|"]
    for name, rs in periods:
        tokens = sum(plan_usage.total_tokens(r.get("tokens") or {}) for r in rs)
        right = sum(1 for r in rs if r.get("savings", 0) > 0)
        cost = sum(r["cost"] for r in rs)
        base = sum(r["baseline_cost"] for r in rs)
        ratio = f"{base / cost:.1f}\u00d7 lighter" if cost > 0 and base / cost >= 1.05 else "about the same"
        lines.append(f"| {name} | {len(rs)} | {right} | {plan_usage.tokens_text(tokens)} | {ratio if rs else '-'} |")

    mix = defaultdict(lambda: {"turns": 0, "tokens": 0})
    for r in rows[-500:]:
        key = f"{pricing.label_of(cfg, r['model'])} @ {r.get('effort') or '?'}"
        mix[key]["turns"] += 1
        mix[key]["tokens"] += plan_usage.total_tokens(r.get("tokens") or {})
    lines += ["", "**Recent model mix** (last 500 tasks)", "",
              "| Setup | Tasks | Tokens |", "|---|---:|---:|"]
    for key, m in sorted(mix.items(), key=lambda kv: -kv[1]["turns"]):
        lines.append(f"| {key} | {m['turns']} | {plan_usage.tokens_text(m['tokens'])} |")

    light_on_premium = [r for r in rows[-200:] if r.get("task_class") in ("trivial", "routine") and r["tier"] >= 3]
    shown, accepted = totals.get("nudges_shown", 0), totals.get("nudges_accepted", 0)
    lines += ["", f"Tips shown: {shown} · acted on: {accepted}"
              + (f" ({round(100 * accepted / shown)}%)" if shown else "")]
    if light_on_premium:
        lines.append(f"Of your last 200 tasks, {len(light_on_premium)} looked light but ran on Opus or Fable. "
                     "Sonnet or Haiku would usually have done, and used less of your limit.")
    lines += ["", "_Token counts are measured. \"Usage vs reference\" is an estimate; see the plugin's METHODOLOGY doc._"]
    return "\n".join(lines)


def savings_report(cfg):
    rows = store.read_ledger()
    totals = store.load_totals()
    money = lambda x: pricing.fmt_money(cfg, x)  # noqa: E731
    base = cfg["baseline"]
    base_label = f"{pricing.label_of(cfg, pricing.resolve_model(cfg, base['model']))} @ {base['effort']}"

    if not rows:
        return ("Token Steward has no completed tasks recorded yet. Savings appear here after your "
                "first few requests.")
    if plan_usage.framing(cfg) == "usage":
        return _usage_report(cfg, rows, totals, base_label)

    now = time.time()
    periods = [
        ("Last 24 hours", [r for r in rows if now - r["ts"] < 86400]),
        ("Last 7 days", [r for r in rows if now - r["ts"] < 7 * 86400]),
        ("This month", [r for r in rows if store.month_key(r["ts"]) == store.month_key(now)]),
        ("All time", rows),
    ]
    lines = ["# Your AI usage and savings", "",
             f"Savings are measured against **{base_label}** (your firm's reference configuration).", "",
             "| Period | Tasks | Spent | Would have cost | Saved |",
             "|---|---:|---:|---:|---:|"]
    for name, rs in periods:
        b = _bucket(rs)
        lines.append(f"| {name} | {b['turns']} | {money(b['cost'])} | {money(b['baseline'])} | **{money(b['savings'])}** |")

    mix = defaultdict(lambda: {"turns": 0, "cost": 0.0})
    for r in rows[-500:]:
        key = f"{pricing.label_of(cfg, r['model'])} @ {r.get('effort') or '?'}"
        mix[key]["turns"] += 1
        mix[key]["cost"] += r["cost"]
    lines += ["", "**Recent model mix** (last 500 tasks)", "",
              "| Configuration | Tasks | Spent |", "|---|---:|---:|"]
    for key, m in sorted(mix.items(), key=lambda kv: -kv[1]["turns"]):
        lines.append(f"| {key} | {m['turns']} | {money(m['cost'])} |")

    light_on_premium = [r for r in rows[-200:] if r.get("task_class") in ("trivial", "routine") and r["tier"] >= 3]
    shown, accepted = totals.get("nudges_shown", 0), totals.get("nudges_accepted", 0)
    lines += ["", f"Tips shown: {shown} · acted on: {accepted}"
              + (f" ({round(100 * accepted / shown)}%)" if shown else "")]
    if light_on_premium:
        extra = sum(r["cost"] for r in light_on_premium)
        lines.append(f"Of your last 200 tasks, {len(light_on_premium)} looked light but ran on Opus/Fable "
                     f"({money(extra)}). Sonnet or Haiku would usually have done.")
    lines += ["", "_Figures are estimates from token counts and list prices; see the plugin's METHODOLOGY doc._"]
    return "\n".join(lines)


def calibration_report(cfg):
    """Observed output tokens per task by effort, vs. the configured multipliers."""
    rows = store.read_ledger()
    by_effort = defaultdict(list)
    for r in rows:
        if r.get("effort"):
            by_effort[r["effort"]].append(r["tokens"].get("output", 0))
    if not by_effort:
        return "No data yet."
    med = statistics.median(by_effort["medium"]) if by_effort.get("medium") else None
    lines = ["| Effort | Tasks | Median output tokens | Observed ratio vs medium | Configured |",
             "|---|---:|---:|---:|---:|"]
    for level in cfg["effort_levels"]:
        vals = by_effort.get(level)
        if not vals:
            continue
        m = statistics.median(vals)
        ratio = f"{m / med:.2f}" if med else "n/a"
        lines.append(f"| {level} | {len(vals)} | {int(m):,} | {ratio} | {cfg['effort_output_multiplier'].get(level)} |")
    lines.append("")
    lines.append("Observed ratios mix effort with task difficulty (people pick higher effort for harder "
                 "work), so treat them as an upper bound when tuning `effort_output_multiplier`.")
    return "\n".join(lines)


def export_csv():
    rows = store.read_ledger()
    buf = io.StringIO()
    fields = ["date", "model", "effort", "task_class", "responses", "input", "output", "cache_write",
              "cache_read", "cost", "baseline", "baseline_cost", "savings", "nudged", "nudge_accepted"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        flat = {k: r.get(k) for k in fields}
        flat.update({k: r["tokens"].get(k, 0) for k in pricing.USAGE_KEYS})
        w.writerow(flat)
    return buf.getvalue()
