"""Work out which model and effort level a prompt is about to run on.

UserPromptSubmit hooks receive neither the model nor the effort, so we infer them from, in order:
  1. Settings written by /model or /effort *after* the last response (the user just switched)
  2. The environment (ANTHROPIC_MODEL, CLAUDE_CODE_EFFORT_LEVEL)
  3. What the previous turn actually ran on (transcript model; effort from the last Stop hook)
  4. Settings files, then the model's default effort
"""

import json
import os

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


def settings_snapshot(cwd):
    """The model and effort values the settings files currently hold. Saved at the end of each turn
    so the next prompt can tell a real /model or /effort switch (the value changed) from an
    unrelated settings write (theme, permissions), which changes the file but not these values."""
    return {"model": _settings_value(cwd, "model")[0], "effort": _settings_value(cwd, "effortLevel")[0]}


def _switched_to(state, key, current):
    seen = (state.get("seen_settings") or {})
    return current if current and key in seen and current != seen[key] else None


def current_model(cfg, hook_input, state):
    cwd = hook_input.get("cwd")
    if os.environ.get("ANTHROPIC_MODEL"):  # overrides settings files
        return pricing.resolve_model(cfg, os.environ["ANTHROPIC_MODEL"])
    settings_model = _settings_value(cwd, "model")[0]
    switched = _switched_to(state, "model", settings_model)
    if switched:
        return pricing.resolve_model(cfg, switched)  # /model since the last response
    last_model, _ = transcript.last_assistant_model(hook_input.get("transcript_path"))
    for candidate in (last_model, state.get("model_at_start"), settings_model):
        key = pricing.resolve_model(cfg, candidate)
        if key:
            return key
    return None


def current_effort(cfg, hook_input, state, model_key, prompt=""):
    cwd = hook_input.get("cwd")
    levels = cfg["effort_levels"]
    if "ultrathink" in (prompt or "").lower():
        return "max"
    env = os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    if env in levels:
        return env
    settings_effort = _settings_value(cwd, "effortLevel")[0]
    switched = _switched_to(state, "effort", settings_effort)
    if switched in levels:
        return switched  # /effort since the last response
    if state.get("last_effort") in levels:
        return state["last_effort"]
    if settings_effort in levels:
        return settings_effort
    tier = pricing.tier_of(cfg, model_key)
    return cfg["default_effort_by_tier"].get(str(tier), "medium") if tier else None
