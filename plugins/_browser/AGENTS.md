# Browser Plugin DOX

## Purpose

- Own the built-in Patchright browser tool and WebUI browser viewer.
- Bridge browser automation, page inspection helpers, and browser panel UI.

## Ownership

- `plugin.yaml` and `default_config.yaml` own metadata and browser settings defaults.
- `tools/browser.py` owns the agent-facing browser tool.
- `helpers/` owns the Patchright runtime, private interactive display, selectors, URL helpers, extension management, and connector runtime logic.
- `api/` owns status, extension, and browser WebSocket handlers.
- `assets/`, `prompts/`, `skills/`, `extensions/`, and `webui/` own browser scripts, prompts, skill guidance, hook contributions, and UI.

## Local Contracts

- Keep browser actions safe around external pages, credentials, and user data.
- Preserve Patchright lifecycle cleanup and WebSocket viewer compatibility across regular host browsers and Electron WebContentsView embedding.
- Keep the WebUI Browser inside its own modal/canvas affordance; do not replace it with page-level navigation.
- Default the visible WebUI Browser to the authenticated Xpra HTML5 viewer for its existing Patchright page. Keep live CDP screencast and lightweight snapshots as automatic fallbacks.
- Do not block an available interactive viewer on a redundant Chromium screenshot; capture initial snapshots only for fallback transports.
- Keep headful Chromium in a normal window with its own toolbar clipped above the private display; do not use browser fullscreen, which shows Chromium's exit warning.
- Persist open-tab ownership and URLs through the shared KVP store; automatically restore the current chat when its Browser surface opens in per-chat mode and every saved chat in shared mode, then hide Chromium's redundant crash-restore advisory.
- When no Browser tab manifest exists yet, use Chromium's last session once to migrate open tabs into the owned manifest.
- Throttle interactive resize updates throughout a drag and let the native-sized Chromium viewport follow the private display; do not defer all layout updates until resizing stops.
- Reuse the private display's native dimensions when interactive-viewer requests omit a size. Page CSS viewport dimensions change with zoom and must not resize the display during navigation or tab switching.
- Keep exactly one interactive viewer iframe connected during canvas/modal handoff so hidden surfaces cannot compete to resize the same display.
- Complete tab switching when the viewer subscription succeeds and reuses the interactive viewer URL; the shared iframe does not reload for each tab. New viewer URLs and fallback frames retain their load/render completion path.
- Notify the active Xpra client of its new frame geometry before resizing the backing display; after an interactive canvas/modal handoff, reconcile once after Xpra's deferred resize so Chromium cannot retain the previous surface size.
- Present the Xpra shadow window as the raw browser canvas: remove its HTML decoration and shadow pointer while preserving exact viewport geometry.
- Keep one internal Chromium, Xvfb, and Xpra runtime per Agent Zero process with one unguessable gateway token.
- Apply the shared `virtual_desktop.XPRA_START_ENV` defaults when launching Xpra; preserve inherited timeout overrides. Disable local shared-memory transport for the WebSocket viewer.
- Synchronous context cleanup shares the named BrowserCleanup event loop. Cancel only the cleanup task on completion/timeout; an individual context must not terminate the shared thread used by concurrent resets.
- Bind Browser Xpra endpoints to loopback, route them through the authenticated virtual-desktop gateway, and keep file transfer, URL opening, printing, and audio disabled.
- Paint live screencast frames through the Browser panel canvas/ImageBitmap path when available; keep the `<img>`/data URL path for snapshots and fallback rendering.
- Push internal screencast frames from the runtime to the WebSocket consumer after subscription; keep `read/pop_screencast_frame` as fallback/tooling APIs, not the WebUI hot path.
- Keep Browser viewer frame transport capability-negotiated: updated clients may request binary/slim screencast frames, while older clients must keep the base64/full-metadata fallback. Do not let the WebUI advertise binary frames unless its Socket.IO client reconstructs attachments as real `Blob`, `ArrayBuffer`, or typed-array values.
- Keep WebUI Browser tabs scoped to the active chat context by default; aggregate tabs from other context handles only when the Browser settings tab scope is `shared`.
- Share one persistent internal-Browser sign-in profile across chats while enforcing tab ownership through context-bound runtime handles; resetting or removing a chat closes only its tabs and never deletes the shared profile.
- On first shared-profile use after an upgrade, adopt the first requesting chat's legacy Browser profile when one exists.
- Empty viewer subscriptions and closing the last tab clear the address, page state, viewer, and switching flags. Context changes invalidate pending surface, subscription, and command results before awaiting session refresh; stale completions must not restore another chat or clear the current startup state. Structured subscription errors release switching state just like transport failures.
- Show an accessible in-panel startup state while the on-demand shared Browser runtime is cold-starting; keep that one runtime warm until Browser configuration changes or Agent Zero shuts down.
- Listing tabs must not cold-start Chromium when there are no saved tabs to restore. Preserve per-chat/shared and legacy-session restoration when saved tabs exist.
- Navigation waits only for the requested readiness: agent tools default to `domcontentloaded`, while WebUI navigation/new tabs and restored tabs use `commit`. Do not follow navigation with another load wait or fixed settle delay; retain settling for interaction actions. Read title, back-navigation availability, and loading state in one page evaluation.
- Keep narrow WebUI Browser controls usable by grouping navigation with Annotate/settings above a full-width address bar.
- For Bring Your Own Browser with an existing host profile, `host_browser_selection` may target automatic host selection, a browser family/id, an HTTP CDP discovery address, or a full DevTools WebSocket endpoint and must be forwarded to the connector runtime as `browser_selection`.
- Browser Settings must refresh connected host-browser inventory while the settings view is open so newly authorized endpoints appear without saving or reopening.
- Browser Settings keeps the Host browser dropdown focused on automatic selection, stable IDs for advertised debug endpoints, and advertised Safari WebDriver targets instead of listing every installed local profile. Describe host access as available through Launcher or A0 CLI without presenting the CLI as the only runtime. Present host-browser setup without an outer container treatment: Chromium-family guidance comes first on the left and Safari/macOS second on the right, with narrow layouts stacking naturally and manual endpoint fallback progressively disclosed. Chrome, Opera, and Edge setup buttons appear only when a compatible connected host advertises that installed browser, then use the authenticated connector bridge to open its fixed internal inspect page; mention Brave, Vivaldi, and Chromium without adding more primary buttons. Safari guidance must name Safari Settings > Advanced > Show features for web developers and Developer > Allow remote automation, and explain its dedicated automation window. An exact legacy endpoint advertised by a connected host migrates to that browser's stable ID in both settings and runtime operations; unmatched custom endpoints remain exact and fail closed. Preserve endpoint path/query case and let the connected host resolve discovery addresses.
- Browser URL-intent handling must only claim web URL schemes and leave custom Agent Zero schemes to their owning surfaces.
- Prefer DOM/CDP browser actions with refs, selectors, frame-chain refs, and screenshots over viewport coordinate input. Coordinates remain a visual fallback.
- Do not hardcode user-specific browser paths or secrets.
- Browser model-preset selection resolves omitted preset fields from `_model_config`'s global `Default` preset, not from an unrelated currently scoped model selection. After the first Browser tool call, use the selected preset for subsequent model turns in that monologue and clear it at monologue end.
- Open-browser runtime state (tab listing, last interacted browser, page content) is per-loop dynamic context: it must flow through the `message_loop_prompts_after` extension into `loop_data.extras_temporary` (rendered as message extras), never into the system prompt, so the system prompt stays cache-stable across turns. The extension must check the profile Browser tool policy first and inject nothing when the tool is blocked.
- Browser tool results serialize minified JSON for agent history; any JSON beautification for display stays plugin-local in the WebUI tool handler (`browser-tool-handler.js`), never in shared `helpers/tool.py` where it would apply to every tool.
- History screenshot capture skips `list`, `state`, `content`, `detail`, `evaluate`, closing actions, and batches containing only those actions. Preserve history previews for other actions and reuse explicit screenshot results without capturing again.
- `evaluate` requires a non-empty `script` string in single and multi calls. Reject missing input instead of evaluating `undefined`; preserve legitimate JavaScript null/undefined results.
- `evaluate_timeout_seconds` is a Browser setting (default 30, finite range 0.1–60 seconds, invalid values rejected), resolved for the requesting chat/project; never accept a model-facing timeout override. It bounds user evaluation and result-state collection. Serialize evaluates per page and interrupt with CDP `Runtime.terminateExecution`. Preserve the document when the original request settles within a 250 ms response grace; reload to commit only for unresolved execution (such as awaited promises). Report any reload or fallback closure in the timeout error. Recovery, fallback page closure, and protocol detachment each have a 5-second bound; report recovery failure rather than success. Never reset the shared browser for an evaluate timeout. Caller cancellation must reach the Browser worker and await its cleanup without stopping the shared thread.
- Host evaluate requires `evaluate_timeout_v1`. Core supplies the settings deadline, dispatches multi calls through the same per-browser grouping as Internal Browser, and waits for `cancel_evaluate` acknowledgement on caller/transport cancellation. The companion connector owns browser-side interruption/recovery and rejects Safari evaluate. A lost acknowledgement is an unconfirmed cancellation error, never proof that JavaScript stopped.
- Clipboard `clipboard_action` reads legacy aliases `operation` and `event_type`; `a0_path` and `context_id` are screenshot result fields, not tool args. Document only canonical args in model-facing prompts.
- Browser action values accept legacy spellings `setactive`/`activate`/`focus` for `set_active`, `typesubmit` for `type_submit`, and `keychord` for `key_chord`; prompts document only canonical action values.
- Annotation mode highlights the DOM element under the pointer, keeps saved overlays page-local, and may batch annotated pages only within the active chat context.
- Quick settings contains the model preset, a scoped Host / Container choice, native container-page zoom, installed Chrome Extensions, and More settings. Keep its rows and actions free of hover tooltips while preserving accessible labels for icon controls. Show the dimmed Configure host browser text button directly below the choice only in Host mode; both settings links reuse the existing plugin config flow. The choice controls agent tool routing; the embedded viewer remains the container browser.
- Browser config owns extension creation, Web Store installation, and agent review actions. Management buttons open Chromium's native history, clear-data, password, contact, extension, and download pages using existing Browser surfaces; keep modal infrastructure unchanged and preserve the settings form underneath.
- Annotation screenshots default off. Capture only explicit annotation selections when the saved scoped preference allows it, never pointer hover; attach images through the chat attachment store only for the current chat, for both typed and voice workflows.
- Native zoom sends only allowlisted shortcuts to Chromium's private display; report the actual device-pixel ratio as the zoom percentage. Chromium retains its native zoom limits and per-site settings.
- Container downloads honor Chromium's native folder and save-dialog preferences. Seed the existing Browser download directory only when no folder is configured, preserve other profile preferences, and restore the native download behavior after Patchright launches.
- Annotation voice input reuses Whisper STT's configured draft/send delivery mode and shared microphone state.
- Internal-browser proxy settings map directly to Playwright's persistent-context proxy option, never to Bring Your Own Browser, and changes must restart active internal runtimes.
- Run internal Chromium headful through Patchright on the private virtual display; do not add user-agent or header spoofing on top of the patched driver.
- Browser keyboard layout settings (`keyboard_layout`/`keyboard_variant`, e.g. `de`/`mac`) apply the configured XKB layout to the private browser display with setxkbmap and pin it on the Xpra shadow server so non-US keyboards type their printed characters; layout changes flow through `browser_runtime_config` and restart internal runtimes. Fallback canvas input forwards AltGraph and macOS Option text without converting ordinary Alt shortcuts into text.
- Browser startup and on-demand launch must converge on the Chromium revision declared by Patchright; let its installer select the host architecture rather than hardcoding x64 or ARM downloads.
- `hooks.prepare_playwright_cache()` owns reconciliation of the pinned Patchright package and Chromium binary so repository self-updates and fresh images use the same setup path.
- `hooks.install()` also installs HTTPX's SOCKS extra in the framework runtime when `socksio` is missing; this supports shared HTTP clients using proxy environment variables independently of Chromium's proxy settings.
- Browser startup must install the shared virtual-desktop route hook itself; do not make Browser depend on the Desktop plugin being enabled.
- Use shared `surface-workspace`, toolbar/control, and separator styles from `webui/css/surfaces.css`; match the lighter Files/Browser panel palette and preserve disabled, active, and keyboard focus states.

## Work Guidance

- Coordinate tool, helper, and panel changes so browser state shown in the UI matches tool behavior.
- Do not depend on nested Electron `<webview>` support or launcher-specific preload bridges unless the launcher exposes that bridge as an explicit contract.
- Keep `prompts/agent.system.tool.browser.md` as a compact callable contract; move detailed browser workflows and host setup/remote-tool fallback guidance into `skills/browser-automation/SKILL.md` so the default system prompt does not name unavailable remote tools.
- Keep `skills/browser-automation/SKILL.md` frontmatter triggers current with rendered browsing, host-browser, screenshot, and web-interaction user phrasing so relevant-skill recall can surface the skill before the full browser workflow is needed.
- Keep fragile form guidance progressively disclosed through `skills/browser-form-workflows/SKILL.md`, linked from the browser prompt through `browser-automation`.

## Verification

- Smoke-test browser launch, navigation, DOM capture, and WebUI viewer after runtime changes.
- For viewer render-path changes, verify direct iframe interaction reaches the same page controlled by Patchright, separate contexts use separate displays, and an unavailable Xpra runtime falls back to CDP screencast/snapshot rendering.
- Run browser prompt/skill regression tests after changing browser prompt or Browser plugin skills.

## Child DOX Index

No child DOX files.
