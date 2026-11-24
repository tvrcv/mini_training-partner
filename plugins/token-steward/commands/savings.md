---
description: Show how much you've spent and saved by right-sizing model and effort
argument-hint: "[--calibration]"
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" report $ARGUMENTS`

Reproduce the report above exactly as written, as Markdown. Do not add commentary, analysis or advice before or after it.
