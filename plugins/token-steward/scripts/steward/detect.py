"""Work out which model and effort level a prompt is about to run on.

UserPromptSubmit hooks receive neither the model nor the effort, so we infer them from, in order:
  1. Settings written by /model or /effort *after* the last response (the user just switched)
  2. The environment (ANTHROPIC_MODEL, CLAUDE_CODE_EFFORT_LEVEL)
  3. What the previous turn actually ran on (transcript model; effort from the last Stop hook)
  4. Settings files, then the model's default effort
"""

import json
import os
from datetime import datetime

from . import pricing, transcript


def _settings_files(cwd):
    home = os.path.expanduser("~")
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude")
    files = [os.path.join(config_dir, "settings.json")]
    if cwd:
        files += [os.path.join(cwd, ".claude", "settings.json"),
                  os.path.join(cwd, ".claude", "settings.local.json")]
    return files  # lowest precedence first


def _settings_value(cwd, key):
    """(value, mtime) from the highest-precedence non-managed settings file that sets key."""
    found = (None, 0.0)
    for path in _settings_files(cwd):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if key in data and data[key]:
                found = (data[key], os.path.getmtime(path))
        except (OSError, ValueError):
            continue
    return found


def _iso_to_epoch(ts):
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def current_model(cfg, hook_input, state):
    cwd = hook_input.get("cwd")
    settings_model, settings_mtime = _settings_value(cwd, "model")
    last_model, last_ts = transcript.last_assistant_model(hook_input.get("transcript_path"))

    if settings_model and settings_mtime > _iso_to_epoch(last_ts) and last_model:
        return pricing.resolve_model(cfg, settings_model)  # switched since the last response
    if os.environ.get("ANTHROPIC_MODEL"):
        return pricing.resolve_model(cfg, os.environ["ANTHROPIC_MODEL"])
    for candidate in (last_model, state.get("model_at_start"), settings_model):
        key = pricing.resolve_model(cfg, candidate)
        if key:
            return key
    return None


def current_effort(cfg, hook_input, state, model_key, prompt=""):
    cwd = hook_input.get("cwd")
    if "ultrathink" in (prompt or "").lower():
        return "max"
    env = os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    if env in cfg["effort_levels"]:
        return env
    settings_effort, _ = _settings_value(cwd, "effortLevel")
    if state.get("last_effort") in cfg["effort_levels"]:
        # If settings changed after we last saw effort, the user ran /effort; prefer settings.
        if settings_effort in cfg["effort_levels"] and settings_effort != state["last_effort"] \
                and _settings_value(cwd, "effortLevel")[1] > state.get("last_effort_ts", 0):
            return settings_effort
        return state["last_effort"]
    if settings_effort in cfg["effort_levels"]:
        return settings_effort
    tier = pricing.tier_of(cfg, model_key)
    return cfg["default_effort_by_tier"].get(str(tier), "medium") if tier else None
