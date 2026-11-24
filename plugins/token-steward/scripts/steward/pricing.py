"""Model resolution and cost arithmetic. All money is USD; prices are per 1M tokens."""

import re

USAGE_KEYS = ("input", "output", "cache_write", "cache_read")


def resolve_model(cfg, model):
    """Map a model id or alias (e.g. 'claude-opus-5-5[1m]', 'opus', 'us.anthropic.claude-sonnet-5-5')
    to a key in cfg['pricing'], or None if unknown."""
    if not model:
        return None
    name = str(model).strip().lower()
    name = re.sub(r"\[.*?\]$", "", name)  # context-window suffix like [1m]
    name = name.split("/")[-1]
    for prefix in ("us.anthropic.", "eu.anthropic.", "apac.anthropic.", "global.anthropic.", "anthropic."):
        if name.startswith(prefix):
            name = name[len(prefix):]
    name = name.split("@")[0]
    if name in cfg["aliases"]:
        name = cfg["aliases"][name]
    pricing = cfg["pricing"]
    if name in pricing:
        return name
    # Longest-prefix match handles dated or suffixed ids (e.g. claude-sonnet-5-5-fast).
    candidates = [key for key in pricing if name.startswith(key)]
    return max(candidates, key=len) if candidates else None


def tier_of(cfg, model_key):
    return cfg["pricing"][model_key]["tier"] if model_key else None


def label_of(cfg, model_key):
    return cfg["pricing"][model_key]["label"] if model_key else "unknown model"


def effort_rank(cfg, effort):
    levels = cfg["effort_levels"]
    return levels.index(effort) if effort in levels else None


def multiplier(cfg, effort):
    return cfg["effort_output_multiplier"].get(effort or "medium", 1.0)


def cost(cfg, model_key, usage):
    """Actual cost of a token usage dict {input, output, cache_write, cache_read} on a model."""
    if not model_key:
        return 0.0
    rates = cfg["pricing"][model_key]
    return sum(usage.get(k, 0) * rates[k] for k in USAGE_KEYS) / 1_000_000


def counterfactual_cost(cfg, usage, actual_effort, target_model_key, target_effort):
    """What the same work would cost on another model/effort.

    Input-side tokens (prompt, context, cache) are held constant: the same conversation would
    have been sent. Output tokens (which include thinking) are scaled by the configured effort
    multipliers, since effort mainly changes how much the model generates.
    """
    scale = multiplier(cfg, target_effort) / max(multiplier(cfg, actual_effort), 1e-9)
    adjusted = dict(usage)
    adjusted["output"] = usage.get("output", 0) * scale
    return cost(cfg, target_model_key, adjusted)


def model_for_tier(cfg, tier):
    """The current-generation model for a tier, via the alias table (haiku/sonnet/opus/fable)."""
    alias = cfg["tier_names"][str(tier)].lower()
    return resolve_model(cfg, alias)


def fmt_money(cfg, amount):
    sym = cfg.get("currency_symbol", "$")
    if abs(amount) >= 100:
        return f"{sym}{amount:,.0f}"
    if abs(amount) >= 0.995:
        return f"{sym}{amount:,.2f}"
    if abs(amount) >= 0.01:
        return f"{sym}{amount:.2f}"
    return f"<{sym}0.01"
