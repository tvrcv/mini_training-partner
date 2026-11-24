# Token Steward for claude.ai (browser extension)

A Chrome/Edge extension that brings Token Steward to claude.ai chat, where plugin hooks don't run.

- **While someone types** a light request on a heavy setup, a short tip appears above the message box. It names the current model and effort, suggests a lighter one with the estimated saving, and says how to switch. Sending as-is always works.
- **When a reply finishes** on a lighter setup than the firm's reference, a thank-you appears with the estimated saving and the month and all-time totals.
- **The toolbar popup** shows savings, replies tracked, tips acted on, the recent model mix, a pause button and CSV export.

It uses the same pricing, reference configuration and classifier as the Claude Code plugin. `tools/build_extension_config.py` copies them from `plugins/token-steward/config/defaults.json` into `src/shared-config.js`.

## How it differs from the Claude Code plugin

| | Claude Code / Cowork plugin | claude.ai extension |
|---|---|---|
| When the tip appears | As the prompt is submitted (affects the next request) | **While typing, before send** |
| Token counts | Measured from the session transcript | **Estimated** from on-screen text (about 4 characters per token, plus hidden reasoning scaled by effort) |
| Can it see the model? | Yes, from the transcript | From the model menu label; stays silent if it can't read it |
| Can it see effort? | Yes, from Claude Code | From the effort or extended-thinking control, when present; otherwise judges on model alone |
| Surfaces | CLI, desktop Code tab, IDEs, Cowork | claude.ai in Chrome or Edge. Not the desktop or mobile apps |

## Privacy

- Runs only on `https://claude.ai/*`. Its only permission is `storage`.
- Never stores or sends what anyone types or receives. Storage holds counts, model, effort, task class and estimated costs, kept in the browser's extension storage (last 2,000 replies).
- Makes no network requests.

## Firm-wide deployment

1. **Publish.** Upload the zipped `extension/` folder (`npm run package:extension`) to the Chrome Web Store as a private listing for your Google Workspace domain, or to Microsoft Edge Add-ons. Self-hosting a `.crx` with an update manifest also works where your IT allows it.
2. **Force-install** it with the browser's enterprise policy: `ExtensionInstallForcelist` in Chrome (Google Admin console, Group Policy or MDM) and the equivalent in Edge.
3. **Configure it** through managed extension policy (Chrome: `3rdparty → extensions → <extension id>`; Google Admin console: *Apps & extensions → the extension → Policy for extensions*). The keys are defined in [`managed_schema.json`](managed_schema.json). Example:

```json
{
  "costFraming": "allowance",
  "baselineModel": "claude-opus-5-5",
  "baselineEffort": "high",
  "mode": "inline",
  "minMessagesBetweenTips": 4
}
```

Set **`costFraming`** to match how your firm pays for claude.ai:

- `dollars` for usage-based billing. Messages show estimated savings in money.
- `allowance` for seat-based plans. Messages talk about stretching usage limits, never dollars. A lighter model on a seat plan doesn't reduce the invoice, so quoting money there would be misleading.

`mode: "confirm"` additionally holds a send **once** for severe mismatches (by default, a trivial request at maximum settings on a top-tier model), with *Send as-is* and *I'll switch first*. We recommend leaving it on `inline`.

## Maintenance: when claude.ai changes

claude.ai isn't a public API, and its page structure changes without notice. All page-specific code is in [`src/dom.js`](src/dom.js). Every lookup tries several selectors and returns nothing when unsure, and the extension stays silent rather than guess. So the usual failure after a claude.ai update is **no tips**, not broken pages.

To fix one without shipping a new version, push replacement selectors through the `selectors` policy key, for example:

```json
{ "selectors": { "modelSelector": "[data-testid=\"new-model-picker\"]" } }
```

Keys: `composer`, `sendButton`, `stopButton`, `modelSelector`, `effortControl`, `assistantMessage`, `userMessage`.

**Assign an owner** who checks the extension against the live site after claude.ai releases. The selectors in `dom.js` are based on claude.ai's markup patterns but haven't been verified against a signed-in session, so that check is the first thing to do before rollout (see below).

## Before rollout: verify against the live site

1. Load it unpacked: `chrome://extensions` → Developer mode → *Load unpacked* → select this `extension/` folder.
2. Open claude.ai, pick Opus with extended thinking or high effort, and type *"Rephrase this email so it sounds more formal"*. A tip should appear above the message box within a second.
3. Send it, switch to Haiku, send another light request. A thank-you should appear top right when the reply finishes.
4. Open the toolbar popup: replies tracked and the model mix should update.

If step 2 shows nothing, open DevTools on claude.ai and check which element holds the model name and the message box, then adjust `DEFAULT_SELECTORS` in `src/dom.js`.

## Development

```bash
python3 tools/build_extension_config.py         # after changing the plugin's defaults.json
node --test tests/extension/core.test.js        # logic, including parity with the Python classifier
node --test tests/extension/e2e.test.js         # loads the real extension in Chromium against a mock chat page
```

The end-to-end test needs Playwright with Chromium (`npm install && npx playwright install chromium`). Set `TS_SCREENSHOT_DIR` to save screenshots of the tip, the thank-you and the popup.
