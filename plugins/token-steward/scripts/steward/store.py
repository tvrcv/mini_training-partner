"""Local persistence: per-session state, a global prefs file, running totals and the turn ledger.

Privacy: nothing here stores prompt or response text. The ledger holds token counts, model,
effort, cost and the task class only. Prompts are reduced to a one-way hash when (and only
when) 'confirm' mode needs to recognise a re-submitted prompt.
"""

import contextlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone

from .config import data_dir


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def _safe_id(session_id):
    return "".join(ch for ch in str(session_id or "unknown") if ch.isalnum() or ch in "-_")[:80]


# ---- per-session state --------------------------------------------------------------------

def session_path(session_id):
    return data_dir() / "sessions" / f"{_safe_id(session_id)}.json"


def load_session(session_id):
    return _read_json(session_path(session_id), {
        "prompt_count": 0,
        "nudges_shown": 0,
        "consecutive_ignored": 0,
        "last_nudge_prompt": None,
        "last_nudge_ts": 0,
        "pending_nudge": None,
        "turn_start_offset": None,
        "task_class": None,
        "nudged_this_turn": False,
        "last_effort": None,
        "last_thanks_ts": 0,
        "session_savings": 0.0,
        "session_cost": 0.0,
        "held_prompt_hashes": [],
        "model_at_start": None,
    })


def save_session(session_id, state):
    _write_json(session_path(session_id), state)


def prune_sessions(max_age_days=30):
    folder = data_dir() / "sessions"
    if not folder.exists():
        return
    cutoff = time.time() - max_age_days * 86400
    for f in folder.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


# ---- user-wide prefs (snooze, banner) ------------------------------------------------------

def prefs_path():
    return data_dir() / "prefs.json"


def load_prefs():
    return _read_json(prefs_path(), {"snooze_until": 0, "last_banner_day": None})


def save_prefs(prefs):
    _write_json(prefs_path(), prefs)


def is_snoozed(prefs=None):
    prefs = prefs or load_prefs()
    return time.time() < prefs.get("snooze_until", 0)


# ---- totals + ledger ------------------------------------------------------------------------

def month_key(ts=None):
    return datetime.fromtimestamp(ts or time.time(), tz=timezone.utc).strftime("%Y-%m")


def load_totals():
    return _read_json(data_dir() / "totals.json", {
        "all_time": {"cost": 0.0, "baseline_cost": 0.0, "savings": 0.0, "turns": 0},
        "by_month": {},
        "nudges_shown": 0,
        "nudges_accepted": 0,
    })


@contextlib.contextmanager
def _locked(name):
    """Exclusive cross-process lock, so parallel sessions don't lose each other's updates."""
    fh = open(data_dir() / f".{name}.lock", "a+")
    try:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        except ImportError:  # Windows
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        fh.close()  # releases the lock


def add_to_totals(record):
    with _locked("totals"):
        return _add_to_totals(record)


def _add_to_totals(record):
    totals = load_totals()
    month = totals["by_month"].setdefault(
        month_key(record["ts"]), {"cost": 0.0, "baseline_cost": 0.0, "savings": 0.0, "turns": 0}
    )
    for bucket in (totals["all_time"], month):
        bucket["cost"] += record["cost"]
        bucket["baseline_cost"] += record["baseline_cost"]
        bucket["savings"] += max(record["savings"], 0.0)
        bucket["turns"] += 1
    totals["nudges_shown"] += 1 if record.get("nudged") else 0
    totals["nudges_accepted"] += 1 if record.get("nudge_accepted") else 0
    _write_json(data_dir() / "totals.json", totals)
    return totals


LEDGER_ROTATE_BYTES = 8 * 1024 * 1024  # ~20,000 tasks; older rows move to a dated archive file


def append_ledger(record):
    path = data_dir() / "ledger.jsonl"
    try:
        if path.stat().st_size > LEDGER_ROTATE_BYTES:
            os.replace(path, data_dir() / f"ledger-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 10**9:09d}.jsonl")
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")


def read_ledger_tail(max_bytes=512 * 1024):
    """Recent rows only, read from the end of the file: keeps the prompt-time path fast."""
    path = data_dir() / "ledger.jsonl"
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            chunk = fh.read()
    except OSError:
        return []
    lines = chunk.splitlines()
    if size > max_bytes:
        lines = lines[1:]  # first line may be cut mid-row
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def read_ledger():
    """Every row, archives included, oldest first (for reports and export)."""
    files = sorted(data_dir().glob("ledger-*.jsonl")) + [data_dir() / "ledger.jsonl"]
    out = []
    for path in files:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out
