"""Usage framing: tokens and plan limits instead of dollars.

Two kinds of number appear in messages:
  * measured: token counts (from the transcript) and session/weekly limit percentages (from the
    status line snapshot, when the person has turned it on and their plan reports limits)
  * estimated: how much more of a limit one setup uses than another. Anthropic doesn't publish
    per-model limit weights, so relative API list price is used as the proxy, and the wording
    always says "about".
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

SNAPSHOT_MAX_AGE = 12 * 3600


def framing(cfg):
    return "dollars" if cfg.get("framing") == "dollars" else "usage"


def snapshot_path():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return Path(base) / "token-steward" / "limits.json"


def read_limits():
    """{'five_hour': {...}, 'seven_day': {...}} from the status line, if recent and still current."""
    try:
        snap = json.loads(snapshot_path().read_text())
    except (OSError, ValueError):
        return {}
    if time.time() - snap.get("ts", 0) > SNAPSHOT_MAX_AGE:
        return {}
    now = time.time()
    out = {}
    for key in ("five_hour", "seven_day"):
        w = snap.get(key)
        if isinstance(w, dict) and (not w.get("resets_at") or float(w["resets_at"]) > now):
            out[key] = w
    return out


def _when(epoch):
    try:
        dt = datetime.fromtimestamp(float(epoch))
    except (TypeError, ValueError, OSError):
        return ""
    return dt.strftime("%H:%M") if dt.date() == datetime.now().date() else dt.strftime("%a %H:%M")


def limits_sentence(limits=None):
    """'You've used 41% of this week's limit (resets Thu 09:00) and 23% of this session's.' or ''."""
    limits = read_limits() if limits is None else limits
    week, session = limits.get("seven_day"), limits.get("five_hour")
    if not week and not session:
        return ""
    bits = []
    if week:
        resets = _when(week.get("resets_at"))
        bits.append(f"{week['used_percentage']:.0f}% of this week's limit" + (f" (resets {resets})" if resets else ""))
    if session:
        bits.append(f"{session['used_percentage']:.0f}% of this session's")
    return "You've used " + " and ".join(bits) + "."


def tokens_text(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M tokens"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k tokens"
    return f"{n} tokens"


def total_tokens(usage):
    return sum(int(usage.get(k, 0) or 0) for k in ("input", "output", "cache_write", "cache_read"))


def ratio_text(ratio):
    """'about 25×' for ratios worth mentioning, else ''."""
    if ratio is None or ratio < 1.5:
        return ""
    return f"about {ratio:.0f}×" if ratio >= 3 else f"about {ratio:.1f}×"
