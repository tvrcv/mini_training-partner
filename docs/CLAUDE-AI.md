# Token Steward on claude.ai: Cowork and chat

Token Steward reaches three surfaces in different ways:

| Surface | What runs | Tips before or after send | Savings counter |
|---|---|---|---|
| Claude Code (CLI, desktop Code tab, IDEs) | Full plugin: hooks, commands, guide skill | Tip as the prompt is submitted | Measured from real token counts |
| Cowork | Full plugin (hooks load in Cowork) | Same as Claude Code | Same as Claude Code |
| claude.ai chat (web, desktop, mobile) | Guide skill only. Chat ignores plugin hooks | None from the plugin itself | None from the plugin itself |
| claude.ai chat in Chrome/Edge | The [browser extension](../extension/README.md) | Inline tip while typing, before send | Estimated from on-screen text |

## 1. Distribute through claude.ai organization settings

One plugin source serves Claude Code, Cowork and chat. An Owner adds this repository as an organization marketplace in claude.ai (**Organization settings → Plugins**) and sets the plugin's availability. Members then find it under **Customize → Plugins**.

Requirements this repo already meets:

- No top-level `bin/` directory in the plugin (claude.ai rejects plugins that have one). Executables live in `scripts/`.
- The plugin source is a relative `./plugins/token-steward` path.

What you must do:

- **Host the marketplace in a private or internal repository** on github.com or gitlab.com. claude.ai only syncs organization marketplaces from private or internal repos.

## 2. Cowork

Cowork loads plugin hooks, so tips and savings messages work as in Claude Code. Before rolling out:

- **Test one Cowork task end to end** with `TOKEN_STEWARD_DEBUG=1` if you can set it. Hooks need `python3` wherever the Cowork session runs. If it isn't there, the hooks are skipped silently and nothing else breaks.
- Check that the switch commands in the tips (`/model …`, `/effort …`) match what your Cowork version offers. If they don't, change `tier_commands` in the org override.

## 3. Chat

Chat loads the **guide** skill, so anyone can ask *"which model should I use for this?"* or *"is Opus overkill for summarising these notes?"* and get an answer based on the firm's playbook. The skill can't see the model picker or token usage, so it can't step in unprompted or count savings.

The plugin's `savings`, `snooze` and `export` commands also appear in chat (chat loads commands as skills). They need a local script, so in chat they reply with a short note to use Claude Code or Cowork instead.

## 4. Tips in chat: the browser extension

For tips in chat itself, deploy the [browser extension](../extension/README.md) to Chrome or Edge through enterprise policy. It shows the tip while someone types, before they send, and a thank-you with estimated savings after the reply. It covers claude.ai in the browser only, not the desktop or mobile apps, and its token counts are estimates from on-screen text.

## 5. A note on what "saved" means in chat

On Team and standard Enterprise seats, chat usage is mostly covered by the seat price. A lighter model there stretches people's usage limits rather than cutting the invoice. On usage-based plans it saves money directly. The browser extension has a setting for this (`costFraming`) so the message it shows matches how your firm actually pays.
