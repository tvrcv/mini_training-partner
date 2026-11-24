"""Read model and token usage from a Claude Code session transcript (JSONL).

Each assistant API response appears as one or more lines with type == "assistant"; lines that
belong to the same response share message.id and repeat its usage, so usage is de-duplicated
by message id.
"""

import json
import os

TAIL_BYTES = 256 * 1024


def file_size(path):
    try:
        return os.path.getsize(path)
    except (OSError, TypeError):
        return 0


def _iter_lines(path, start_offset=0):
    try:
        with open(path, "rb") as fh:
            fh.seek(start_offset)
            for raw in fh:
                try:
                    yield json.loads(raw)
                except ValueError:
                    continue
    except (OSError, TypeError):
        return


def _is_real_user_prompt(entry):
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    return False


def _usage_of(message):
    u = message.get("usage") or {}
    return {
        "input": u.get("input_tokens", 0) or 0,
        "output": u.get("output_tokens", 0) or 0,
        "cache_write": u.get("cache_creation_input_tokens", 0) or 0,
        "cache_read": u.get("cache_read_input_tokens", 0) or 0,
    }


def turn_usage(path, start_offset=None):
    """Aggregate usage of assistant responses for the current turn.

    With start_offset (recorded when the prompt was submitted), read from there. Without it
    (e.g. the plugin was enabled mid-session), fall back to everything after the last real
    user prompt. Returns (usage_by_model, n_responses) where usage_by_model maps a raw model id
    to a usage dict.
    """
    if start_offset is not None and start_offset <= file_size(path):
        entries = list(_iter_lines(path, start_offset))
    else:
        entries = list(_iter_lines(path, max(0, file_size(path) - 4 * TAIL_BYTES)))
        last_prompt = max((i for i, e in enumerate(entries) if _is_real_user_prompt(e)), default=-1)
        entries = entries[last_prompt + 1:]

    by_id = {}
    for e in entries:
        if e.get("type") != "assistant":
            continue
        msg = e.get("message") or {}
        model = msg.get("model")
        if not model or model.startswith("<"):  # e.g. "<synthetic>" local messages
            continue
        key = msg.get("id") or e.get("uuid")
        by_id[key] = (model, _usage_of(msg))

    by_model = {}
    for model, usage in by_id.values():
        agg = by_model.setdefault(model, {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0})
        for k, v in usage.items():
            agg[k] += v
    return by_model, len(by_id)


def last_assistant_model(path):
    """(model_id, iso_timestamp) of the most recent main-thread assistant response, or (None, None)."""
    found = (None, None)
    for e in _iter_lines(path, max(0, file_size(path) - TAIL_BYTES)):
        if e.get("type") == "assistant" and not e.get("isSidechain"):
            model = (e.get("message") or {}).get("model")
            if model and not model.startswith("<"):
                found = (model, e.get("timestamp"))
    return found
