"""Local, zero-cost task-complexity heuristic.

Deliberately not an LLM call: the guardrail must add no latency and no token spend of its own.
It only needs to be right often enough to start a useful conversation, and it errs toward
silence: anything ambiguous is classed 'routine' or 'complex', and complex work is never nudged.
"""

import re
from functools import lru_cache

CODE_FENCE = re.compile(r"```")
FILE_REF = re.compile(r"(@[\w./-]+|\b[\w-]+\.(py|ts|tsx|js|java|go|rs|sql|ipynb|xlsx|pptx|docx|csv)\b)", re.IGNORECASE)


@lru_cache(maxsize=64)
def _compile(pattern):
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


def classify(cfg, prompt):
    """Return (task_class, score, matched_signal_names)."""
    c = cfg["classifier"]
    text = (prompt or "").strip()
    words = len(text.split())
    score = 0
    matched = []

    for signal in c["signals"]:
        if _compile(signal["pattern"]).search(text):
            score += signal["weight"]
            matched.append(signal["name"])

    heavy = any(sig["weight"] > 0 and sig["name"] in matched for sig in c["signals"])
    if words <= c["short_prompt_words"] and not heavy:
        score -= 1
    elif words >= c["long_prompt_words"]:
        score += 2
        matched.append("long, detailed brief")

    fences = len(CODE_FENCE.findall(text)) // 2
    files = len(set(m[0] for m in FILE_REF.findall(text)))
    if fences >= 2 or files >= 4:
        score += 2
        matched.append("multiple files / code blocks")

    # Slash commands and very short continuations ("yes", "go ahead") carry no signal about the
    # task itself; they continue whatever was already under way.
    if text.startswith("/") or words <= 3:
        return "continuation", score, matched

    has_light_signal = any(
        s["weight"] < 0 and s["name"] in matched for s in c["signals"]
    )
    if score >= c["complex_min_score"]:
        task_class = "complex"
    elif has_light_signal and score <= c["trivial_max_score"]:
        task_class = "trivial"
    elif has_light_signal and score <= c["routine_max_score"]:
        task_class = "routine"
    else:
        # No clear evidence either way: stay quiet.
        task_class = "general"
    return task_class, score, matched
