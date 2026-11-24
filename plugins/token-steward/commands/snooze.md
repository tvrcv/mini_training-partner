---
description: Pause Token Steward tips (default 4 hours). Use "off" to resume.
argument-hint: "[hours|off]"
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" snooze $ARGUMENTS`

Repeat the line above to the user verbatim and nothing else.
