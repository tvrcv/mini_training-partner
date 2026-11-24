---
description: Export your Token Steward usage ledger as CSV (no prompt text is ever stored)
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" export > token-steward-usage.csv && echo "Saved token-steward-usage.csv in $(pwd)"`

Repeat the line above to the user verbatim and nothing else.
