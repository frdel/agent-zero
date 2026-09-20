# A0 Connector Plugin DOX

## Purpose

- Own the current Agent Zero connector plugin for HTTP and WebSocket integration.
- Provide remote execution, text-editing freshness, and connector runtime bridges.

## Ownership

- `plugin.yaml` owns plugin metadata and settings scope.
- `api/` owns connector WebSocket and API entry points.
- `helpers/` owns chat context, event bridge, execution config, freshness, version, and WebSocket runtime helpers.
- `tools/`, `prompts/`, `skills/`, `extensions/`, and `webui/` own connector-facing agent and UI contributions.

## Local Contracts

- `tools/text_editor_remote.py` logs `type="text_editor"` through a `get_log_object()` override so the WebUI routes its messages through the `_text_editor` plugin's `get_message_handler` JS extension; keep remote edits visually consistent with local edits.
- Remote text editing reuses the shipped `_text_editor` patch and log helpers. Disabling local editor discovery does not remove these Python modules; removing the bundled dependency is unsupported.
- Preserve session-auth and `auth.handlers` activation assumptions.
- Keep remote tool prompts synchronized with remote tool behavior and disclose
  them only from connected CLI metadata: no connected CLI hides all remote tool
  prompts, remote file metadata enables `text_editor_remote`, F4-enabled remote
  execution metadata enables `code_execution_remote` and `input_remote`, and supported enabled
  Computer Use that does not need re-arming enables `computer_use_remote`.
- Remote execution uses the same runtime set as local code execution. `input_remote`
  mirrors local `input`, forwarding trimmed `keyboard` through gated terminal
  execution with framework-owned `allow_running`. It shares connection, write
  access, timeout, transfer, and disconnect handling; ordinary model args cannot
  enable `allow_running`. There is no `runtime=input` or `code` input alias.
- Computer Use prompts keep `element_index` top-level and semantic `target` syntax in backend skills. macOS `app-scoped-semantic-targeting` enables explicit app/window scope; older clients use the indexed window workflow. Native `get_window_state.mode` only labels output and stays out of model-facing guidance.
- `computer_use_remote` starts a missing chat session inside the first requested action only after the host returns `COMPUTER_USE_SESSION_REQUIRED` before dispatch. Start once on the same socket/context and resume with the returned session ID and a fresh operation ID. Never auto-replace an explicit session binding, retry permission/ambiguous failures, or start from `status`/`stop_session`; keep existing host enablement, trust, and platform approval checks. Attach the requested action's capture, not an extra startup capture.
- Host Computer Use skills begin with `list_windows` or `capture`. Linux X11/XWayland viewer guidance lives in `skills/host-computer-use-linux/references/x11-viewers.md` and requires independently enabled host code execution for shell techniques. Permission denials remain stop conditions; the internal Docker/Xpra desktop and standalone X11 backend selection are unchanged.
- Agent-scoped skill discovery includes this plugin's `skills/` root only when a routed connected socket has connector capability metadata. WebUI-only sockets do not qualify; disabled capabilities still count as a connected CLI. Filter roots on each discovery without mutating cached paths or persisting visibility settings. `setup-a0-cli` lives in the bundled `_skills` collection (`plugins/_skills/skills/`) and stays discoverable while disconnected.
- Never re-add a connector prompt that the effective project/profile tool policy
  blocks.
- Do not bypass WebSocket authentication or leak connector session data.
- Host Files transfers use authenticated HTTP for both directions. Download receipts use opaque, request-scoped slots in server-owned temporary directories; the protected `file_browser_transfer` API rejects expired slots, enforces byte limits and rechecks host access. Cleanup and receipt publication share a lock so late requests cannot recreate expired files. WebSocket control/results retain the negotiated limits. Editor inherits the configurable File Browser text limit (10 MiB by default).
- Context kill/remove extensions release pending transfer state synchronously before task shutdown and send best-effort abort notices on the shared background worker, covering native Stop/reset/delete as well as Connector routes.
- HTTP capabilities and `connector_hello` advertise
  `capabilities.ws_max_payload_bytes`. Store the peer ceiling per authenticated
  SID, remove it on disconnect, and use the 4 MiB legacy floor when absent or
  invalid. Every connector event sent to that SID must pass the ceiling to the
  shared WebSocket manager; oversize becomes a structured
  `PAYLOAD_TOO_LARGE` error and never a transport disconnect. Mirror the same
  limit into the manager's live connection state so Socket.IO acknowledgements
  are constrained after their final result envelope is assembled.
- `helpers/file_browser.py` registers the bundled live host-folder provider for Files. Discover CLI sessions and the unique active Launcher gateway through existing routing; never choose an ambiguous gateway or expose raw socket IDs. Bind each virtual folder to the socket and exposed root, recheck scopes on every operation, and reject stale folders after disconnect/root changes. Older connectors show an update/restart hint. Host settings remain in the CLI/Launcher; Files cannot change their scopes or exposed path. This is filesystem access, not a Launcher control surface.
- Advertise Launcher gateways additively through HTTP capability
  `launcher_gateway` and WebSocket feature `launcher_gateway_control`. Older
  ordinary CLI clients retain their existing protocol fields and behavior; do
  not provide a partial tools-only fallback when either feature is absent.
- A Launcher `connector_hello` carries a versioned gateway object with kind,
  stable ID, host label, and bounded status. Store it per authenticated socket,
  remove it on disconnect, and let context-bound CLI sockets retain routing
  priority. One unique Launcher gateway may be the global fallback. A duplicate
  socket with the same ID replaces stale state; distinct simultaneous IDs fail
  closed as Multiple hosts.
- `connector_gateway_control` and `connector_gateway_control_result` cover
  master state, complete scope replacement, and Disconnect
  (`emergency_disconnect` on the wire). Protected
  WebUI mutations require CSRF, await the matching acknowledgement, and return
  refreshed status. Apply acknowledged master and scope state to remote file
  and execution routing before resolving the control request; the follow-up
  `connector_hello` only reconciles metadata. Never let the WebUI select a host
  folder or personal browser profile.
- Launcher gateway scopes expose file reading and writing separately. File
  writing depends on reading, and Code execution depends on file writing. Keep
  older gateway declarations without `file_write` read/write compatible.
- Agent Zero WebUI exposes no Launcher gateway icon, menu, status, or control
  bridge. Host access settings, Disconnect/Reconnect, scope changes, and
  Computer Use approval belong only to attached or detached A0 Launcher chrome.
  Keep the authenticated gateway HTTP/WebSocket protocol available for the
  Launcher and connector runtime without adding a Core WebUI surface.
- HTTP capabilities and `connector_hello` advertise `transfer_protocol=1`.
  Eligible large file, exec, Computer Use, browser, and gateway requests/results
  use one symmetric start, ordered 64 KiB chunk, end, and abort contract with
  declared size and SHA-256. Bound each receive by the local ceiling, four
  concurrent transfers per SID, a 30-second idle timeout, and disk spooling
  above 1 MiB. Resolve a pending operation only after exact size, order, hash,
  JSON object shape, and operation ID all verify. Missing capability and legacy
  file chunks fail once with a structured error and do not disconnect the SID.
- Associate transfer state with the operation's existing context. Pause, reset,
  and delete abort matching transfers; disconnect aborts all SID-owned state.
  Mark outbound loops before emitting abort so raw payloads and pending futures
  are released promptly even when the peer disappears mid-frame.
- `text_editor_remote` is a bounded text control plane. Core must reject write
  and patch content over 256 KiB before creating a pending WebSocket operation;
  the CLI independently enforces the same ceiling. Reads return at most 2,000
  lines or 256 KiB with continuation metadata and reject binary-looking files.
  Prompts must direct complete or binary transfer to authenticated HTTP.
- Host browser status metadata may advertise `available_browsers` entries with browser ids, labels, CDP endpoints, status, and enabled state; keep older CLI payloads without those fields compatible.
- `computer_use_remote` action results may report `requested_dispatch`, `actual_dispatch`, and `foreground_fallback_used` (`fallback_used` legacy); these are output-only fields, not tool args. `scroll` reads `dx`/`dy` with legacy aliases `delta_x`/`delta_y`; document only canonical args in model-facing prompts.
- `computer_use_remote` reads legacy `name` as an `operation` fallback for element/ax/uia actions; it stays out of model-facing prompts.
- Model preset definitions exposed through v1 are global; project arguments select scope but never create project-owned definitions. Model switcher state reports the effective main, utility, and embedding models and preserves embedding-change notifications.
- The protected v1 `agent_editor` route delegates to the bundled Agent Editor
  API and must not define another profile schema or write profile files itself.
- The protected v1 `agents_list` response uses the shared agent presentation
  catalog rather than applying connector-specific visibility rules.
- Computer Use receipts describe transport success unless the connector returns explicit effect evidence. Linux target-bound typing requires a verified active/focused `window_id`; window activation uses focus, never a press action on an application or window node. Do not retry an identical failed Computer Use call.
- Accepted WebSocket user-message replay metadata may include attachment basenames only; strip paths, query strings, fragments, and bytes before logging them in `kvps`.

## Work Guidance

- Coordinate connector runtime changes with API, tools, prompts, and WebUI viewer behavior together.

## Verification

- Run connector-specific tests or smoke-test HTTP and `/ws` integration when changing runtime behavior.
- Cross-platform first-call session startup and no-retry boundaries are covered in the sibling connector's `tests/test_plugin_backend.py`; Core prompt gating remains covered by `tests/test_a0_connector_prompt_gating.py`.
- Launcher gateway regression coverage lives in
  `tests/test_a0_connector_launcher_gateway.py`.

## Child DOX Index

No child DOX files.

Host Files forwards Core transfer/text limits without an independent HTTP cap. Older Connector clients retain their existing cap until updated and restarted.

- The host provider implements the same streaming `read(relative, destination, limit)` / `write(relative, source, expected)` contract as the five community providers. HTTP file bodies stay in private temporary files and shared bounded copies; no whole-file bytes return from provider reads.

- Incoming host HTTP transfers pass the upload stream to `file_transfers.write_stream_atomic`, retaining integrity receipts and the operation limit.
