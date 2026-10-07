# WebUI JavaScript DOX

## Purpose

- Own shared frontend JavaScript modules, client-side infrastructure, API helpers, WebSocket clients, stores, extension loaders, and UI utilities.
- Keep frontend contracts stable for core UI and plugin extensions.

## Ownership

- `AlpineStore.js` owns store creation and persistence helpers.
- `api.js` owns CSRF-aware HTTP helpers.
- `websocket.js` owns browser WebSocket client behavior.
- `extensions.js` owns frontend extension loading.
- `components.js` owns `<x-component>` loading, component caching, module injection, nested component processing, and `globalThis.xAttrs`.
- `modals.js` owns the stacked modal shell, `openModal`, `closeModal`, `scrollModal`, footer relocation, backdrop, and modal z-index behavior.
- `surfaces.js` owns shared surface registration, right-canvas/modal mode routing, surface modal action rails, and reusable draggable/focus modal chrome.
- `initFw.js` owns Alpine bootstrap and custom lifecycle directives such as `x-create`, `x-destroy`, and periodic `x-every-*` hooks.
- `overflow.js` owns the reusable `x-overflow` directive for constrained flex rows. It observes layout and late plugin content, collapses trailing controls behind `more_horiz`, and opens their original panels without moving or reinitializing Alpine nodes.
- `icons.js` owns `<x-icon>`, icon-name validation, the name property/attribute bridge, and helpers that read or update both the first-party custom element and legacy plugin ligature spans.
- `messages.js` owns native message/process-step rendering, safe Markdown and HTML conversion, and KaTeX delimiter handling.
- `messages.js` routes unhandled log types through `drawMessageTool`, preserving generic tool-step presentation. Before raw-log grouping it resolves unregistered types from cached and incoming records through `getMessageHandler`; types selecting `drawMessageTool` join the process-step set. Explicit custom standalone handlers remain standalone. Keep the legacy `drawMessageDefault` export for plugin compatibility.
- `messages.js` owns `drawMessageAgent` kvps rendering order: `thoughts`, `tool_name`, `tool_args` keys (spread per-key under actual names, not a sub-table, skipping reserved keys), then `step` at the end. Reserved keys (`thoughts`, `step`, `reasoning`, `tool_name`, `tool_args`, `args`, `headline`) win over any colliding `tool_args` key. The `response` tool check is hoisted to skip arg rendering entirely for response turns.
- `messages.js` owns `Scroller` smooth-scroll suppression for `GEN` process steps (live agent responses) to prevent streamed-content jumpiness; non-`GEN` steps keep smooth scrolling.
- `message-collapse.js` owns the layout-safe overflow measurement shared by collapsible user messages and responses.
- `message-window.js` owns the bounded, tail-first raw-log window used by message rendering.
- `loading-indicators.js` owns reusable DOM factories for shared loading visuals.
- `scroller.js` owns bottom-following snapshots and cancellation of pending scroll effects.
- Other modules own focused UI utilities such as modals, messages, safe markdown, shortcuts, TTS/STT, surfaces, and initialization.

## Local Contracts

- Use ES modules and browser-compatible JavaScript.
- `x-overflow` follows `display: contents` wrappers to find flex items. Each collapsible item is a button or contains a trigger; its sibling `[x-show]`, `[role=menu]`, `[role=dialog]`, or `[data-overflow-panel]` is reused as the submenu. `data-overflow-label` on the trigger may override its rendered label. Keep the row's containing flex item shrinkable (`min-width: 0`); non-control content stays inline. Native manual popovers preserve DOM scope while avoiding clipping and stacking conflicts. Resize/mutation observers and document listeners must be removed on unmount.
- Overflow labels open submenus on hover and toggle them on click; a click-closed submenu stays closed until pointer exit or another click. When neither side has room, use the larger space above/below the first menu and scroll the submenu, keeping its label reachable.
- Mark a compound visual with `data-overflow-icon` on the trigger or a child (for example, an avatar or percentage ring). Overflow entries mirror its rendered markup and updates without cloning Alpine bindings or interactive buttons; font icons, SVGs, and images are detected by default. Controls without a visual reserve no icon space.
- Overflow measurements allow half a CSS pixel of rounding tolerance: browser zoom can make summed item rectangles and CSS gaps slightly exceed a shrink-wrapped row even when every control fits. Verify both fitting and genuinely constrained rows at native browser zoom levels.
- Create dynamic Material Symbols with `document.createElement("x-icon")` and assign `.name`; generated HTML uses an empty `<x-icon name="..."></x-icon>`. Shared helpers that can receive third-party plugin DOM must continue accepting legacy `.material-symbols-outlined` and `.material-icons-outlined` spans.
- Route JSON and fetch calls through `api.js` unless a caller has a specific nonstandard transport contract.
- `callJsonApi()` is for JSON request/response flows and must preserve CSRF/auth behavior.
- `fetchApi()` must continue adding CSRF headers, retrying 403 CSRF refresh paths, and redirecting to `/login` when required.
- `createStore(name, model)` must continue working before and after Alpine boots by proxying to the raw model first and Alpine store later.
- `saveState()` and `loadState()` must not persist functions and should support include/exclude filtering for transient fields.
- `openModal(path)` returns a promise that resolves when that modal DOM node is removed; invalid paths show an in-modal error instead of rejecting.
- Opening the same modal path multiple times must continue creating multiple stack entries; no dedupe is assumed.
- `closeModal()` with no path closes the top modal; `closeModal(path)` closes that path wherever it is in the stack; missing paths are no-ops.
- Modal stack semantics are top-modal-first for Escape, close buttons, z-index, and backdrop placement.
- Restorable modal state is session-scoped and opt-in; surface modals may set `data-modal-restore="surface"` and `modals.js` restores only those path-based surface windows after reload navigation. Browser hard-refresh is still reported to app code as reload, so do not treat this as durable cross-session UI state.
- The modal shell structure is `.modal` > `.modal-inner` > `.modal-header`, `.modal-scroll` containing `.modal-bd`, and `.modal-footer-slot`.
- `data-modal-footer` content is relocated from modal body into `.modal-footer-slot`.
- Click-outside close requires both `mousedown` and `mouseup` on the outer `.modal` container.
- `scrollModal(id)` scrolls inside the top modal's `.modal-scroll`.
- Keep extension loader cache keys and extension point names stable for plugins.
- The rendered index supplies a complete `runtimeInfo.webuiExtensions` manifest; `extensions.js` must resolve HTML and JavaScript extension paths from it without per-extension-point startup API calls, while retaining `/api/load_webui_extensions` as a compatibility fallback when the manifest is unavailable.
- HTML extension loading turns discovered HTML files into `<x-component>` tags; JavaScript extensions must export a default function.
- `extensions.js` exposes `initialHtmlExtensionsLoaded` and emits `webui-extensions-loaded` once after Alpine and the initial recursive component/extension loading placeholders have cleared.
- Transport-level preloading must remain outside `components.js`, `extensions.js`, and `initFw.js`; cache hits flow through their ordinary asynchronous requests.
- `<x-component>` loading must process component `style`, `script`, and stylesheet-link assets only once, even when a component keeps its scoped `<style>` inside `<body>`.
- Every `<x-component>` instance must await cached module-load promises before markup is appended so Alpine bindings only run after imported stores exist.
- Frontend extension hooks such as `confirm_dialog_after_render` and `get_tool_message_handler` must preserve their mutable context contracts.
- Sanitize or safely render user/model-provided HTML and markdown.
- Convert standard TeX delimiters before Markdown parsing without touching inline or fenced code. Keep thought-card math rendering local to the agent-message handler rather than adding math flags to generic process-step or key/value rendering.
- Do not expose secrets in localStorage, console logs, URLs, or WebSocket payloads.
- Full message snapshots that start at backend log `no` 0 must replace the current message DOM before rendering; incremental snapshots should keep patching existing messages.
- The state request builder advertises collection-delta support. An incremental snapshot may carry `contexts: null` and `tasks: null`; retain the current stores and skip sidebar selection/fallback reconciliation in that case. Extension hooks still receive the cached full collections so existing plugin contracts remain list-shaped.
- Root responses render with safe Markdown and LaTeX throughout live updates and completion. GEN process steps render thoughts and tool args as plain text without KaTeX, so `$$`-style sequences in technical prose stay literal.
- Shared path linking recognizes plain paths, `file:///` URLs, and `/api/download_work_dir_file?path=` text, including inline code, while preserving existing anchors and fenced code blocks.
- User sends render optimistically with their backend message ID; the matching log update must merge into that existing row rather than duplicate it.
- Incremental message rendering must update standard action handlers without remounting unchanged button nodes or removing extension-owned actions.
- Long histories stay cached as raw log data but render a contiguous tail-first DOM window. The initial base view contains one 60-entry page; after paging, the base window contains two aligned pages, retaining the adjacent page and discarding only the far page in either direction. Visible boundaries expand to whole logical process groups so a page never reconstructs a partial group; the unit classifier must include plugin-backed process steps such as `code_exe`, and oversized groups use their own 50-step incremental window. A capped process group rebuilds only when a newly added step advances that window; updates to an existing step patch it in place. Paging must preserve a visible anchor and occur at the scroll boundary after user intent, using passive loading indicators rather than count-bearing controls. Live entries and late content growth follow the tail until the reader deliberately moves away; historical window rebuilds must cancel pending auto-scroll effects, render in an off-screen staging history, and atomically swap fully laid-out content into the live scroller before restoring its anchor.
- Message-window cache identity must keep different log types distinct even when they share a backend ID; root-agent GEN and response records intentionally use the same ID and must both survive replay, while same-ID/same-type updates still replace their earlier cached version.
- Process-group IDs belong only to the `.process-group` element, never its wrapper. Fallback group lookup inspects only the final message container so later steps and responses cannot cross a standalone-message boundary.
- Utility records join a process render unit only when a substantive process step follows before the next standalone boundary. Group visibility must use that full-log classification rather than infer utility-only state from partially mounted DOM children. Standalone utility-only runs must not wrap root responses or reopen completed groups, and their group chrome stays hidden unless utility messages are enabled.
- `PROCESS_STEP_TYPES` contains core log types only. `messages.js` dispatches `get_process_step_types` with a fresh `{ processStepTypes: Set }` before merging each batch. Extensions add their types and dispatch identifies generic tool fallbacks; the pure classifier receives the resulting set for grouping and utility lookahead, without knowing its source. Do not add a separate handler cache or persist declarations beyond the extension loader lifecycle.
- Warnings classified into a full-log process render unit must remain process steps during replay even when the current DOM tail is already complete; use the live DOM tail only when render metadata is unavailable.
- `set_messages_after_loop` receives offscreen live updates as results with `result.virtualized === true` and `result.element === null`; extensions that only need `args` may still react, while DOM-mutating extensions must guard the element.
- Context switches, log GUID resets, and full log snapshots must reset both message DOM and message-window cache state.
- Awaited message-window layout frames must have a timer fallback so hidden or occluded browser windows cannot block state synchronization on painting.
- Context switches clear stale history immediately but defer the chat loading splash for 300 ms so fast loads do not flash; slower loads fade it in and dismiss it only after the matching context snapshot finishes rendering. Stale snapshots and timers must not affect a newer switch's splash.
- Long primary-agent responses start collapsed only during chat replay; long user-message text starts collapsed during both live sends and replay. Both use the shared collapsible-message behavior, but user attachments remain outside its clipped content target.
- Collapse controls must appear only after a measurable message body exceeds the 15em preview. Treat hidden or zero-width chat geometry as indeterminate, remeasure replayed messages after their staging-to-live swap, and remeasure observed groups when their layout changes.
- Info log entries with `kvps.finished` complete the active process group and clear its running treatment.

## Work Guidance

- Prefer small named exports over adding globals.
- Keep frontend API payload assumptions synchronized with backend handlers.
- Use existing modal, notification, cache, device, and surface utilities before adding new infrastructure.
- Check plugin extension callers before changing shared extension behavior.
- Preserve the single shared modal shell and backdrop model; do not add a parallel overlay implementation.
- Preserve modal z-index spacing with a stable base stack and a shared backdrop below the active modal.
- Keep the shared modal stack above the mobile right-canvas rail so blocking modals remain authoritative on small screens.
- If opening a new modal from a close handler, schedule it with `requestAnimationFrame` to avoid stack removal races.
- Keep modal state cleanup explicit because stores can outlive their DOM.
- Device-specific styling may rely on the `device-touch` or `device-mouse` body class set during initialization.

## Verification

- Run targeted frontend/WebUI tests when available.
- For message math changes, smoke-test both response Markdown and agent thought cards with inline and display TeX.
- Manually smoke-test startup, API calls, WebSocket state sync, and affected UI flows after infrastructure changes.
- For modal infrastructure, verify duplicate paths can stack, missing paths stay closable, Escape closes only the top modal, and click-outside requires both mouse down and mouse up on the overlay container.

## Child DOX Index

No child DOX files.
