---
description: Pause Token Steward tips (default 4 hours). Use "off" to resume.
argument-hint: "[hours|off]"
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" snooze $ARGUMENTS`

Repeat the line above to the user verbatim and nothing else.

If there is no command output above (for example the line still shows the literal command, or is empty), say only: "This command needs Claude Code or Cowork, where Token Steward can measure usage. In claude.ai chat, ask me which model fits a task instead."
