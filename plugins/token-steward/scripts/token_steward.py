#!/usr/bin/env python3
"""Token Steward entry point.

  token_steward.py hook <session-start|user-prompt-submit|stop>   (reads hook JSON on stdin)
  token_steward.py report [--calibration]
  token_steward.py export
  token_steward.py snooze [hours|off]

Hook mode always exits 0 and prints nothing on error: a guardrail must never break a session.
Set TOKEN_STEWARD_DEBUG=1 to see errors on stderr.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from steward import config, hooks, report, store  # noqa: E402

HANDLERS = {
    "session-start": hooks.on_session_start,
    "user-prompt-submit": hooks.on_user_prompt_submit,
    "stop": hooks.on_stop,
}


def run_hook(event):
    try:
        raw = sys.stdin.read()
        inp = json.loads(raw) if raw.strip() else {}
        out = HANDLERS[event](config.load_config(), inp)
        if out:
            sys.stdout.write(json.dumps(out))
    except Exception as exc:  # fail open
        if os.environ.get("TOKEN_STEWARD_DEBUG"):
            import traceback
            traceback.print_exc()
            print(f"token-steward: {exc}", file=sys.stderr)
    return 0


def run_snooze(arg):
    prefs = store.load_prefs()
    if arg in ("off", "resume", "0"):
        prefs["snooze_until"] = 0
        store.save_prefs(prefs)
        print("Token Steward tips are back on.")
        return 0
    try:
        hours = float(arg) if arg else 4.0
    except ValueError:
        hours = 4.0
    hours = min(max(hours, 0.25), 24 * 7)
    prefs["snooze_until"] = time.time() + hours * 3600
    store.save_prefs(prefs)
    until = time.strftime("%a %H:%M", time.localtime(prefs["snooze_until"]))
    print(f"Token Steward tips paused until {until}. Usage is still recorded so your savings stay "
          f"accurate. Resume early with /token-steward:resume")
    return 0


def main(argv):
    # Slash commands pass the hooks' data folder explicitly, so both read and write the same place.
    if "--data-dir" in argv:
        i = argv.index("--data-dir")
        value = argv[i + 1] if i + 1 < len(argv) else ""
        argv = argv[:i] + argv[i + 2:]
        if value and "${" not in value:
            os.environ["TOKEN_STEWARD_DATA_DIR"] = value
    if len(argv) >= 2 and argv[0] == "hook" and argv[1] in HANDLERS:
        return run_hook(argv[1])
    cfg = config.load_config()
    if argv and argv[0] == "report":
        print(report.calibration_report(cfg) if "--calibration" in argv else report.savings_report(cfg))
        return 0
    if argv and argv[0] == "export":
        sys.stdout.write(report.export_csv())
        return 0
    if argv and argv[0] == "snooze":
        return run_snooze(argv[1] if len(argv) > 1 else "")
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
