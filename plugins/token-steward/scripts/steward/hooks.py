"""Hook handlers. Each takes the hook's stdin JSON and returns the JSON to print (or {}).

Design rules that every handler follows:
  * Never slow anyone down: no network on the prompt path, no LLM calls, fail open on any error.
  * Inform, don't police: in the default 'advise' mode nothing is ever blocked.
  * Be sparing: cooldowns, a per-session cap, and back-off when tips keep being ignored.
  * Be honest: every savings figure names the configuration it is compared against.
"""

import getpass
import hashlib
import json
import os
import socket
import time
import urllib.request
from datetime import datetime, timezone

from . import classifier, detect, pricing, store, transcript
from . import usage as plan_usage

PREFIX = "Token Steward · "

CLASS_PHRASES = {
    "trivial": "a quick, lightweight request",
    "routine": "a routine request",
}


# ---- helpers ---------------------------------------------------------------------------------

def _switch_model(cfg, tier):
    """How to move to a tier here. Cloud sessions (claude.ai/code) don't take /model shortcuts,
    so there we point at the model menu instead."""
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return f"pick {cfg['tier_names'][str(tier)]} in the model menu under the message box"
    return cfg["tier_commands"][str(tier)]


def _switch_effort(effort):
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return f"set effort to {effort} in the same menu"
    return f"/effort {effort}"


def _severity(cfg, model_key, effort, rec):
    model_gap = max(0, pricing.tier_of(cfg, model_key) - rec["tier"])
    cur_rank = pricing.effort_rank(cfg, effort)
    rec_rank = pricing.effort_rank(cfg, rec["effort"])
    effort_gap = max(0, cur_rank - rec_rank) if cur_rank is not None else 0
    return 2 * model_gap + effort_gap, model_gap, effort_gap


def _typical_usage(cfg, task_class):
    """This user's median-ish turn size for the class (last 50 turns), else configured defaults."""
    rows = [r for r in store.read_ledger_tail() if r.get("task_class") == task_class][-50:]
    if len(rows) >= 5:
        usage = {}
        for k in pricing.USAGE_KEYS:
            values = sorted(r["tokens"].get(k, 0) for r in rows)
            usage[k] = values[len(values) // 2]
        return usage, "medium"  # stored tokens are real; treat as observed at their own effort
    return dict(cfg["default_turn_tokens"].get(task_class) or cfg["default_turn_tokens"]["general"]), "medium"


def _estimate_saving(cfg, task_class, cur_model, cur_effort, rec_model, rec_effort):
    usage, ref_effort = _typical_usage(cfg, task_class)
    now = pricing.counterfactual_cost(cfg, usage, ref_effort, cur_model, cur_effort or ref_effort)
    rec = pricing.counterfactual_cost(cfg, usage, ref_effort, rec_model, rec_effort)
    pct = round(100 * (now - rec) / now) if now > 0 else 0
    return now - rec, pct


def _nudge_allowed(cfg, state):
    n = cfg["nudge"]
    if not n.get("enabled", True) or store.is_snoozed():
        return False
    if state["nudges_shown"] >= n["max_nudges_per_session"]:
        return False
    if state["consecutive_ignored"] >= n["stop_after_consecutive_ignored"]:
        return False
    if state["last_nudge_prompt"] is not None:
        if state["prompt_count"] - state["last_nudge_prompt"] < n["min_prompts_between_nudges"]:
            return False
        if time.time() - state["last_nudge_ts"] < n["min_minutes_between_nudges"] * 60:
            return False
    return True


def _build_nudge(cfg, state, task_class, matched, model_key, effort, rec, model_gap, effort_gap, prompt):
    rec_model = pricing.model_for_tier(cfg, rec["tier"]) if model_gap else model_key
    rec_effort = rec["effort"] if effort_gap else effort
    saving, pct = _estimate_saving(cfg, task_class, model_key, effort, rec_model, rec_effort)
    ratio = 1 / (1 - pct / 100) if 0 < pct < 100 else None

    light = [m for m in matched if any(s["name"] == m and s["weight"] < 0 for s in cfg["classifier"]["signals"])]
    what = CLASS_PHRASES.get(task_class, "a lighter request")
    if light:
        what += f" ({', '.join(light[:2])})"

    current = f"{pricing.label_of(cfg, model_key)}" + (f" at {effort} effort" if effort else "")
    target = f"{pricing.label_of(cfg, rec_model)}" + (f" at {rec_effort} effort" if rec_effort else "")
    steps = []
    if model_gap:
        steps.append(_switch_model(cfg, rec["tier"]))
    if effort_gap:
        steps.append(_switch_effort(rec_effort))

    msg = (f"{PREFIX}This looks like {what}. You're on {current}, which is built for complex, "
           f"multi-step work. {target} typically handles requests like this just as well")
    if plan_usage.framing(cfg) == "dollars":
        if saving >= 0.005 and pct > 0:
            msg += f", at about {pct}% lower cost (≈{pricing.fmt_money(cfg, saving)} per request like this)"
    elif plan_usage.ratio_text(ratio):
        msg += f", and uses {plan_usage.ratio_text(ratio)} less of your usage limit (estimate)"
    msg += f". To switch for what follows: {' then '.join(steps)}."
    if plan_usage.framing(cfg) == "usage" and plan_usage.limits_sentence():
        msg += " " + plan_usage.limits_sentence()
    if "ultrathink" in (prompt or "").lower():
        msg += " Note: 'ultrathink' raises this prompt to maximum reasoning, which is rarely needed here."
    msg += " Your request is running as-is."
    if state["nudges_shown"] == 0:
        msg += " (Pause tips any time with /token-steward:snooze.)"
    return msg, rec_model, rec_effort


def _post_telemetry(cfg, record):
    t = cfg.get("telemetry") or {}
    if not t.get("endpoint"):
        return
    payload = dict(record)
    payload["session"] = hashlib.sha256(str(record.get("session", "")).encode()).hexdigest()[:16]
    if t.get("include_user_id"):
        ident = f"{getpass.getuser()}@{socket.gethostname()}"
        payload["user"] = hashlib.sha256(ident.encode()).hexdigest()[:16]
    req = urllib.request.Request(
        t["endpoint"], data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=t.get("timeout_seconds", 2)).close()
    except Exception:
        pass  # telemetry must never affect the session


def _upgrade_gap(cfg, model_key, effort):
    """How far below the 'complex work' setup the session is (same scale as nudge severity)."""
    target = cfg["upgrade"]["target"]
    model_gap = max(0, target["tier"] - pricing.tier_of(cfg, model_key))
    cur = pricing.effort_rank(cfg, effort)
    effort_gap = max(0, pricing.effort_rank(cfg, target["effort"]) - cur) if cur is not None else 0
    return 2 * model_gap + effort_gap, model_gap, effort_gap


def _build_upgrade(cfg, matched, model_key, effort, model_gap, effort_gap):
    target = cfg["upgrade"]["target"]
    heavy = [m for m in matched if any(s["name"] == m and s["weight"] > 0 for s in cfg["classifier"]["signals"])]
    what = "complex, multi-step work" + (f" ({', '.join(heavy[:2])})" if heavy else "")
    rec_model = pricing.model_for_tier(cfg, target["tier"]) if model_gap else model_key
    current = pricing.label_of(cfg, model_key) + (f" at {effort} effort" if effort else "")
    better = pricing.label_of(cfg, rec_model) + (f" at {target['effort']} effort" if effort_gap else "")
    steps = []
    if model_gap:
        steps.append(_switch_model(cfg, target["tier"]))
    if effort_gap:
        steps.append(_switch_effort(target["effort"]))
    return (f"{PREFIX}This looks like {what}. You're on {current}. For work like this, {better} usually "
            f"gets it right first time, which costs less than several retries. To switch: "
            f"{' then '.join(steps)}. Your request is running as-is.")


def milestone_crossed(milestones, before, after):
    """The highest milestone passed when a running total moved from `before` to `after`, else None."""
    crossed = [m for m in milestones if before < m <= after]
    return max(crossed) if crossed else None


# ---- SessionStart ----------------------------------------------------------------------------

def on_session_start(cfg, inp):
    sid = inp.get("session_id")
    state = store.load_session(sid)
    if inp.get("model"):
        state["model_at_start"] = inp["model"]
    state["seen_settings"] = detect.settings_snapshot(inp.get("cwd"))
    store.save_session(sid, state)

    if inp.get("source") not in (None, "startup"):
        return {}
    store.prune_sessions()

    banner = cfg.get("session_banner") or {}
    prefs = store.load_prefs()
    today = datetime.now().strftime("%Y-%m-%d")
    if not banner.get("enabled", True) or store.is_snoozed(prefs):
        return {}
    if banner.get("once_per_day", True) and prefs.get("last_banner_day") == today:
        return {}
    prefs["last_banner_day"] = today
    store.save_prefs(prefs)

    week_ago = time.time() - 7 * 86400
    week = [r for r in store.read_ledger_tail() if r.get("ts", 0) >= week_ago]
    week_saved = sum(max(r.get("savings", 0.0), 0.0) for r in week)
    light = sum(1 for r in week if plan_usage.is_right_sized(cfg, r))
    model_key = pricing.resolve_model(cfg, inp.get("model"))
    msg = (f"{PREFIX}Match the model to the task: Haiku for quick edits and lookups, Sonnet for "
           f"everyday drafting and coding, Opus or Fable for genuinely hard problems.")
    if model_key:
        msg += f" This session starts on {pricing.label_of(cfg, model_key)}."
    if plan_usage.framing(cfg) == "dollars":
        if week_saved >= 0.01:
            msg += (f" Last 7 days: {pricing.fmt_money(cfg, week_saved)} saved across {light} right-sized "
                    f"task{'s' if light != 1 else ''}.")
    else:
        if plan_usage.limits_sentence():
            msg += " " + plan_usage.limits_sentence()
        if week:
            week_tokens = sum(plan_usage.total_tokens(r.get("tokens") or {}) for r in week)
            msg += (f" Last 7 days: {plan_usage.tokens_text(week_tokens)} across {len(week)} "
                    f"task{'s' if len(week) != 1 else ''}, {light} of them right-sized.")
    msg += " Playbook: /token-steward:guide"
    return {"systemMessage": msg}


# ---- UserPromptSubmit ------------------------------------------------------------------------

def on_user_prompt_submit(cfg, inp):
    sid = inp.get("session_id")
    prompt = inp.get("prompt") or ""
    state = store.load_session(sid)
    state["prompt_count"] += 1
    state["turn_start_offset"] = transcript.file_size(inp.get("transcript_path"))
    state["nudged_this_turn"] = False

    task_class, _score, matched = classifier.classify(cfg, prompt)
    if task_class != "continuation":
        state["task_class"] = task_class

    out = {}
    rec = cfg["recommendations"].get(task_class)
    model_key = detect.current_model(cfg, inp, state)
    effort = detect.current_effort(cfg, inp, state, model_key, prompt)
    state["predicted_model"], state["predicted_effort"] = model_key, effort

    if rec and model_key:
        severity, model_gap, effort_gap = _severity(cfg, model_key, effort, rec)
        n = cfg["nudge"]
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        if prompt_hash in state["held_prompt_hashes"]:
            # A re-send after a 'confirm' hold: the person has decided. Let it through quietly.
            state["held_prompt_hashes"].remove(prompt_hash)
        elif severity >= n["min_severity"] and _nudge_allowed(cfg, state):
            msg, rec_model, rec_effort = _build_nudge(
                cfg, state, task_class, matched, model_key, effort, rec, model_gap, effort_gap, prompt)
            state["nudges_shown"] += 1
            state["last_nudge_prompt"] = state["prompt_count"]
            state["last_nudge_ts"] = time.time()
            state["nudged_this_turn"] = True
            state["pending_nudge"] = {
                "prompt": state["prompt_count"],
                "from_tier": pricing.tier_of(cfg, model_key),
                "from_effort_rank": pricing.effort_rank(cfg, effort),
            }
            if n.get("mode") == "confirm" and severity >= n["confirm_min_severity"]:
                state["held_prompt_hashes"] = (state["held_prompt_hashes"] + [prompt_hash])[-20:]
                out = {"decision": "block", "reason": msg.replace(
                    " Your request is running as-is.",
                    " Switch first, or press Enter on the same prompt again to run it as-is.")}
            else:
                out = {"systemMessage": msg}

        if task_class == "trivial" and n.get("concise_hint_for_trivial") and out.get("decision") != "block":
            out.setdefault("hookSpecificOutput", {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "This request looks simple. Answer directly and concisely; "
                                     "avoid extended exploration unless it is actually needed.",
            })

    up = cfg.get("upgrade") or {}
    if task_class == "complex" and model_key and up.get("enabled", True) and not out \
            and state.get("upgrades_shown", 0) < up.get("max_per_session", 2) and _nudge_allowed(cfg, state):
        gap, model_gap, effort_gap = _upgrade_gap(cfg, model_key, effort)
        if gap >= up.get("min_gap", 2):
            out = {"systemMessage": _build_upgrade(cfg, matched, model_key, effort, model_gap, effort_gap)}
            state["upgrades_shown"] = state.get("upgrades_shown", 0) + 1
            state["last_nudge_prompt"] = state["prompt_count"]
            state["last_nudge_ts"] = time.time()

    store.save_session(sid, state)
    return out


# ---- Stop ------------------------------------------------------------------------------------

def on_stop(cfg, inp):
    sid = inp.get("session_id")
    path = inp.get("transcript_path")
    state = store.load_session(sid)
    by_model, n_responses = transcript.turn_usage(path, state.get("turn_start_offset"))
    state["turn_start_offset"] = transcript.file_size(path)  # a resumed turn won't be double-counted
    if n_responses == 0:
        store.save_session(sid, state)
        return {}

    effort = (inp.get("effort") or {}).get("level") or state.get("predicted_effort")
    if effort in cfg["effort_levels"]:
        state["last_effort"] = effort
    state["seen_settings"] = detect.settings_snapshot(inp.get("cwd"))

    base = cfg["baseline"]
    base_key = pricing.resolve_model(cfg, base["model"])
    totals_usage = {k: 0 for k in pricing.USAGE_KEYS}
    cost = baseline_cost = 0.0
    primary, primary_out = None, -1
    for raw_model, usage in by_model.items():
        key = pricing.resolve_model(cfg, raw_model)
        if not key:
            continue  # unknown/unpriced model: don't guess
        cost += pricing.cost(cfg, key, usage)
        baseline_cost += pricing.counterfactual_cost(cfg, usage, effort, base_key, base["effort"])
        for k in pricing.USAGE_KEYS:
            totals_usage[k] += usage[k]
        if usage["output"] > primary_out:
            primary, primary_out = key, usage["output"]
    if primary is None:
        store.save_session(sid, state)
        return {}
    savings = baseline_cost - cost

    # Did the person act on an earlier tip? (Judged on what actually ran, not on settings.)
    accepted = False
    pending = state.get("pending_nudge")
    if pending and state["prompt_count"] > pending["prompt"]:
        tier_now = pricing.tier_of(cfg, primary)
        rank_now = pricing.effort_rank(cfg, effort)
        if tier_now < pending["from_tier"] or (
                rank_now is not None and pending["from_effort_rank"] is not None
                and rank_now < pending["from_effort_rank"]):
            accepted = True
            state["pending_nudge"] = None
            state["consecutive_ignored"] = 0
        elif state["prompt_count"] - pending["prompt"] >= 2:
            state["pending_nudge"] = None
            state["consecutive_ignored"] += 1

    now = time.time()
    record = {
        "v": 1,
        "ts": now,
        "date": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds"),
        "session": sid,
        "model": primary,
        "tier": pricing.tier_of(cfg, primary),
        "effort": effort,
        "task_class": state.get("task_class"),
        "responses": n_responses,
        "tokens": totals_usage,
        "cost": round(cost, 6),
        "baseline": f"{base_key}@{base['effort']}",
        "baseline_cost": round(baseline_cost, 6),
        "savings": round(savings, 6),
        "nudged": bool(state.get("nudged_this_turn")),
        "nudge_accepted": accepted,
    }
    record["right_sized"] = plan_usage.is_right_sized(cfg, record)
    right_sized = record["right_sized"]
    limits = plan_usage.read_limits()
    if limits:
        record["limits_pct"] = {k: round(v["used_percentage"], 1) for k, v in limits.items()}
    store.append_ledger(record)
    totals = store.add_to_totals(record)
    state["session_cost"] += cost
    state["session_savings"] += max(savings, 0.0)
    _post_telemetry(cfg, record)

    out = {}
    money = lambda x: pricing.fmt_money(cfg, x)  # noqa: E731
    cel = cfg.get("celebrations") or {}
    celebration = ""
    dollars = plan_usage.framing(cfg) == "dollars"
    if cel.get("enabled", True) and (savings > 0 if dollars else right_sized):
        if plan_usage.framing(cfg) == "dollars":
            after = totals["all_time"]["savings"]
            reached = milestone_crossed(cel.get("milestones_usd", []), after - savings, after)
            done = f"saved the firm {money(reached)}" if reached else ""
        else:
            after = totals["all_time"].get("right_sized", 0)
            reached = milestone_crossed(cel.get("milestones_right_sized_tasks", []), after - 1, after)
            done = f"right-sized {reached} tasks" if reached else ""
        if reached:
            celebration = (f"\U0001F389 Milestone: you've now {done}. Thank you, this is exactly the habit "
                           f"that adds up. ")
        elif accepted and totals.get("nudges_accepted") == 1:
            celebration = "\U0001F389 Your first tip acted on. Thank you! "

    th = cfg.get("thanks") or {}
    cooled = now - state.get("last_thanks_ts", 0) >= th.get("min_minutes_between_messages", 15) * 60
    worth_thanking = savings >= th.get("min_turn_savings_usd", 0.01) if dollars else right_sized
    if th.get("enabled", True) and not store.is_snoozed() and worth_thanking \
            and (accepted or cooled or celebration):
        month = totals["by_month"].get(store.month_key(now), {}).get("savings", 0.0)
        opener = "" if celebration else "Thanks for switching, and for considering your usage. " if accepted \
            else "Thank you for considering your usage. "
        setup = f"{pricing.label_of(cfg, primary)}{f' @ {effort}' if effort else ''}"
        reference = f"{pricing.label_of(cfg, base_key)} @ {base['effort']}"
        if plan_usage.framing(cfg) == "dollars":
            msg = (f"{PREFIX}{celebration}{opener}This task ran on {setup} for {money(cost)}, about "
                   f"{money(savings)} less than {reference}. You've saved the business "
                   f"{money(state['session_savings'])} this session, {money(month)} this month and "
                   f"{money(totals['all_time']['savings'])} in total.")
        else:
            ratio = baseline_cost / cost if cost > 0 else None
            week_ago = now - 7 * 86400
            right_week = sum(1 for r in store.read_ledger_tail() if r.get("ts", 0) >= week_ago
                             and plan_usage.is_right_sized(cfg, r))
            msg = (f"{PREFIX}{celebration}{opener}This task used {plan_usage.tokens_text(plan_usage.total_tokens(totals_usage))} "
                   f"on {setup}")
            if plan_usage.ratio_text(ratio):
                msg += f", {plan_usage.ratio_text(ratio)} less of your usage limit than {reference} would take (estimate)"
            msg += f". Right-sized tasks in the last 7 days: {right_week}."
            if plan_usage.limits_sentence():
                msg += " " + plan_usage.limits_sentence()
        out = {"systemMessage": msg}
        state["last_thanks_ts"] = now

    store.save_session(sid, state)
    return out
