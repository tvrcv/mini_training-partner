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


def data_dir():
    """Persistent per-user storage. CLAUDE_PLUGIN_DATA survives plugin updates."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(
        os.path.expanduser("~"), ".claude", "token-steward"
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path
