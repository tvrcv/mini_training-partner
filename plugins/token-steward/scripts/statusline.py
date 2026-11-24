#!/usr/bin/env python3
"""Token Steward status line for Claude Code.

Shows the current model and how much of your 5-hour session limit and weekly limit you've used,
and saves those numbers so Token Steward's tips and thank-yous can quote them.

Claude Code passes plan-limit data only to the status line (field `rate_limits`, for claude.ai
Pro, Max and Ultra subscribers, after the first response of a session), which is why this exists.

Self-contained and standard-library only: `/token-steward:setup-statusline` copies it to
~/.claude/token-steward/statusline.py so it keeps working across plugin updates.
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


def state_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    path = Path(base) / "token-steward"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_snapshot(limits):
    snap = {"ts": time.time()}
    for key in ("five_hour", "seven_day"):
        w = limits.get(key) if isinstance(limits, dict) else None
        if isinstance(w, dict) and isinstance(w.get("used_percentage"), (int, float)):
            snap[key] = {"used_percentage": float(w["used_percentage"]), "resets_at": w.get("resets_at")}
    if len(snap) == 1:
        return
    target = state_dir() / "limits.json"
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".limits-")
    with os.fdopen(fd, "w") as fh:
        json.dump(snap, fh)
    os.replace(tmp, target)


def when(epoch):
    try:
        dt = datetime.fromtimestamp(float(epoch))
    except (TypeError, ValueError, OSError):
        return ""
    if dt.date() == datetime.now().date():
        return dt.strftime("%H:%M")
    return dt.strftime("%a %H:%M")


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        data = {}
    parts = []
    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    limits = data.get("rate_limits") or {}
    try:
        save_snapshot(limits)
    except OSError:
        pass
    session, week = limits.get("five_hour"), limits.get("seven_day")
    if isinstance(session, dict) and session.get("used_percentage") is not None:
        parts.append(f"session {session['used_percentage']:.0f}% (resets {when(session.get('resets_at'))})")
    if isinstance(week, dict) and week.get("used_percentage") is not None:
        parts.append(f"week {week['used_percentage']:.0f}% (resets {when(week.get('resets_at'))})")
    if len(parts) <= 1:
        parts.append("limits appear after the first reply")
    print("Token Steward │ " + " │ ".join(parts))


if __name__ == "__main__":
    main()
