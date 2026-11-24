---
description: Show your session and weekly limit usage under the message box, and in Token Steward's tips
model: haiku
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" setup-statusline || python "${CLAUDE_PLUGIN_ROOT}/scripts/token_steward.py" setup-statusline`

Repeat the message above to the user verbatim and nothing else.

If there is no command output above (for example the line still shows the literal command, or is empty), say only: "This command needs Claude Code on your computer."
