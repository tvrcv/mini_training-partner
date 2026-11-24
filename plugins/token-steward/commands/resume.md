---
description: Turn Token Steward tips back on after a snooze
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" --data-dir "${CLAUDE_PLUGIN_DATA}" snooze off || python "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" --data-dir "${CLAUDE_PLUGIN_DATA}" snooze off`

Repeat the line above to the user verbatim and nothing else.

If there is no command output above (for example the line still shows the literal command, or is empty), say only: "This command needs Claude Code or Cowork, where Token Steward can measure usage. In claude.ai chat, ask me which model fits a task instead."
