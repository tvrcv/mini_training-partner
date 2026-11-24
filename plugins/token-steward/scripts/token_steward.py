#!/usr/bin/env python3
"""Token Steward entry point.

  token_steward.py hook <session-start|user-prompt-submit|stop>   (reads hook JSON on stdin)
  token_steward.py report [--calibration]
  token_steward.py export
  token_steward.py snooze [hours|off]
  token_steward.py setup-statusline

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


def run_setup_statusline():
    """Copy the status line script to a stable place and switch it on in user settings.

    Never replaces a status line someone already has: it says how to combine them instead.
    """
    import shutil
    from pathlib import Path

    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"))
    target = config_dir / "token-steward" / "statusline.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "statusline.py"), target)
    command = f'python3 "{target}" || python "{target}"'

    settings_path = config_dir / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    except ValueError:
        print(f"Your settings file ({settings_path}) isn't valid JSON, so I left it alone. Fix it, then run "
              f"this again, or add this yourself:\n\n\"statusLine\": {{\"type\": \"command\", \"command\": {json.dumps(command)}}}")
        return 0
    existing = settings.get("statusLine")
    if existing and "token-steward" not in json.dumps(existing):
        print("You already have a status line, so I didn't replace it. To show your session and weekly "
              f"limits in Token Steward's tips, have your status line script also pipe its input to:\n\n  {command}")
        return 0
    settings["statusLine"] = {"type": "command", "command": command}
    tmp = settings_path.with_suffix(".json.token-steward-tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, settings_path)
    print("Done. The Token Steward status line is on: under the message box you'll see your model and, after "
          "the first reply, how much of your session and weekly limits you've used. Tips and thank-yous will "
          "quote those numbers too. (Plan limits are reported on Pro, Max and Ultra plans. Cloud sessions "
          "don't read your personal settings, so they won't show it.)")
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
    if argv and argv[0] == "setup-statusline":
        return run_setup_statusline()
    if argv and argv[0] == "snooze":
        return run_snooze(argv[1] if len(argv) > 1 else "")
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
