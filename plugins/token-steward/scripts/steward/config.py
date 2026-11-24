"""Configuration loading: packaged defaults, deep-merged with an optional org override file."""

import json
import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = PLUGIN_ROOT / "config" / "defaults.json"


def _deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = dict(base)
    for key, value in override.items():
        merged[key] = _deep_merge(base.get(key), value) if key in base else value
    return merged


def load_config():
    with open(DEFAULTS_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    override_path = os.environ.get("TOKEN_STEWARD_CONFIG")
    if override_path:
        try:
            with open(os.path.expanduser(override_path), encoding="utf-8") as fh:
                cfg = _deep_merge(cfg, json.load(fh))
        except (OSError, ValueError):
            # A broken org override must never break anyone's session; fall back to defaults.
            pass
    # Two convenience env overrides so admins can steer the baseline from managed settings `env`.
    if os.environ.get("TOKEN_STEWARD_BASELINE_MODEL"):
        cfg["baseline"]["model"] = os.environ["TOKEN_STEWARD_BASELINE_MODEL"]
    if os.environ.get("TOKEN_STEWARD_BASELINE_EFFORT"):
        cfg["baseline"]["effort"] = os.environ["TOKEN_STEWARD_BASELINE_EFFORT"]
    return cfg


def _find_plugin_data():
    """The plugin data folder the hooks write to, for callers that weren't given it.

    Hooks receive CLAUDE_PLUGIN_DATA; slash-command scripts may not. The folder is named after
    the plugin's install id (e.g. token-steward-ai-stewardship, token-steward-synced), so look
    for the most recently used one that holds Token Steward data.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    root = Path(config_dir) / "plugins" / "data"
    candidates = [d for d in root.glob("token-steward*") if (d / "totals.json").exists() or (d / "ledger.jsonl").exists()]
    return max(candidates, key=lambda d: d.stat().st_mtime) if candidates else None


def data_dir():
    """Persistent per-user storage. CLAUDE_PLUGIN_DATA survives plugin updates.

    Order: TOKEN_STEWARD_DATA_DIR (set by --data-dir), CLAUDE_PLUGIN_DATA (hooks), the plugin's
    data folder found on disk, then ~/.claude/token-steward.
    """
    base = (os.environ.get("TOKEN_STEWARD_DATA_DIR") or os.environ.get("CLAUDE_PLUGIN_DATA")
            or _find_plugin_data()
            or os.path.join(os.path.expanduser("~"), ".claude", "token-steward"))
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path
