# Chat Components DOX

## Purpose

- Own chat composer, attachments, message queue, navigation, and top-section component groups.

## Ownership

- `input/` owns composer input, progress, banners, and bottom action bars.
- `attachments/` owns drag/drop and attachment preview UI.
- `message-queue/` owns queued message display and store state.
- `navigation/` owns chat navigation state.
- `top-section/` owns chat header/top area.
- `model-gate-store.js` and `model-setup-gate.html` own the deferred in-thread model setup gate.
- Gate dispatch (`dispatchPendingIfConfigured`) captures `pending` before awaiting and uses that object for the payload; re-check its identity and the send latch after readiness resolves. Keep pending state and session recovery until the send is accepted. Busy sends defer retry until `sendMessage` settles; readiness and preset-editor reads use the pending chat's context. A retry for another context must never enter the selected chat's queue.

## Local Contracts

- Preserve Store Gating for all store-backed chat components.
- Use shared API, WebSocket, notification, and attachment helpers where available.
- Do not bypass CSRF or WebSocket state-sync expectations.
- The shared composer can be mounted on the Welcome screen with no selected chat; sending from that state must create and select a chat context before dispatch.
- Text-only and attachment sends must render the first user turn immediately with the request message ID so the backend log merges into the same row.
- Unsent composer text is kept as a separate browser-session draft for each selected chat and restored when switching contexts; a Welcome-screen prompt must follow the chat created for its first send. Preset changes and setup-gate retries must preserve any new unsent composer draft.
- Composer text uses the main UI font by default; typing a triple-backtick fence and pressing Enter turns that line into a visual code block that serializes back to fenced Markdown, while pasted fenced Markdown stays plain text.
- The contenteditable composer sizes naturally between its CSS minimum and maximum heights; do not freeze measured scroll heights into pixels during mounting or editing.
- The backend rejects dispatches when no chat model is configured: a `user_message_ui` extension in `_model_config` flags the chat and `/message_async` returns a `model_not_configured` payload before logging or dispatching. The client opens the setup gate from that response and must not round-trip a per-send configuration pre-check.
- While the setup gate is open, the composer remains typeable but send is blocked until setup succeeds.
- The setup gate must delegate Cloud/Local setup, account connections, and advanced model configuration to the existing onboarding and model-preset editor modals; do not duplicate provider/model/key forms inline.
- A connected OAuth account without Main/Utility model selection is its own gate state; route to model configuration and do not select models automatically.
- Model setup surfaces that change readiness must notify the gate with `model-setup-changed`, `model-configured`, or an existing modal/onboarding completion signal so the pending prompt can retry automatically.
- Rapid sends (clicks or Enter presses) cannot dispatch duplicate `/message_async` calls: an in-flight send makes further `sendMessage` invocations no-ops until the first completes, before backend `running` state flips.
- Composer pause state is optimistic: a click in flight suppresses poll-snapshot writes to the pause flag until its request settles.
- The top-section project selector, clock, and connection indicator must respect the instance-level mobile/desktop visibility preferences.
- While the selected context is running, an empty composer makes the primary button stop the active run; typed text still adds to the queue, and Enter with an empty composer still sends queued messages.
- Pending queue items render image thumbnails from local blob URLs until the upload confirms; confirmed attachments use server `image_get` URLs, and a failed queue add drops its pending entry.
- Chat navigation controls must cross virtual message-window boundaries; top and bottom target the full cached history rather than only the mounted DOM slice.
- The page-wide attachment drop overlay must activate only for external file drags so internal WebUI drag interactions keep their own targets.

## Work Guidance

- Keep composer and attachment changes responsive across desktop and mobile.
- The selector strip injected into `input/progress.html` uses shared `x-overflow` behavior; controls that do not fit stay reachable through the ellipsis menu, including late plugin additions. Preserve the separate full-width goal strip and speech-stop action.
- Coordinate payload changes with backend chat, upload, and WebSocket handlers.

## Verification

- Smoke-test sending, queued messages, attachments, drag/drop, and navigation after visible changes.
- Smoke-test the unconfigured first-send gate and automatic dispatch after model setup when touching model setup or send interception.

## Child DOX Index

No child DOX files.
