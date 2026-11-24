---
description: Compare observed output tokens per effort level with Token Steward's savings assumptions
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" --data-dir "${CLAUDE_PLUGIN_DATA}" report --calibration || python "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" --data-dir "${CLAUDE_PLUGIN_DATA}" report --calibration`

Reproduce the table and note above exactly as written, as Markdown, with nothing added.

If there is no command output above (for example the line still shows the literal command, or is empty), say only: "This command needs Claude Code or Cowork, where Token Steward can measure usage. In claude.ai chat, ask me which model fits a task instead."
