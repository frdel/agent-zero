# message.py DOX

## Purpose

- Own the `message.py` API endpoint.
- This module submits a user message and runs agent processing synchronously through the UI API.
- Keep this file-level DOX profile synchronized with `message.py` because this directory is intentionally flat.

## Ownership

- `message.py` owns the runtime implementation.
- `message.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `Message` (`ApiHandler`)
  - `async process(self, input: dict, request: Request) -> dict | Response`
  - `async respond(self, task: DeferredTask, context: AgentContext)`
  - `async communicate(self, input: dict, request: Request)`

## Runtime Contracts

- Shared PostgreSQL chats route text and stable message IDs through `communicate_remote(..., ui=True)` before local context creation, UI extension hooks or logging. A first message with no chat ID derives a stable chat identity from its message ID, so a lost acknowledgement cannot create another chat. The claimed execution worker journals UI-hook intent/result and logs only prepared input. A known preparation is reused; an unknown hook outcome is held. UI interventions during an active turn require an explicit input-hook adapter and are rejected. Multipart attachments enter encrypted context resources before admission; JSON `resources` references must already belong to that context. The owner materializes verified bytes before hooks/history. Local/off upload behavior stays unchanged.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `Message` is an `ApiHandler`.
- `Message` defines `process(...)`.
- The `user_message_ui` extension point runs before logging and dispatch; when extension data carries `model_not_configured`, `communicate` returns no task and the response payload reports `"model_not_configured": true` with the context id instead of logging or dispatching the message.
- Observed side-effect areas: filesystem reads, filesystem writes, settings/state persistence, scheduler state.
- Imported dependency areas include: `agent`, `helpers`, `helpers.api`, `helpers.defer`, `helpers.security`, `os`.

## Key Concepts

- Important called helpers/classes observed in the source: `request.content_type.startswith`, `self.use_context`, `mq.log_user_message`, `self.communicate`, `self.respond`, `task.result`, `request.files.getlist`, `files.get_abs_path`, `request.get_json`, `extension.call_extensions_async`, `context.communicate`, `os.makedirs`, `UserMessage`, `safe_filename`, `attachment.save`, `context.get_agent`, `os.path.join`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Related tests observed by source search:
  - `tests/email_parser_test.py`
  - `tests/rate_limiter_test.py`
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_chat_compaction.py`
  - `tests/test_docker_release_plan.py`
  - `tests/test_document_query_fallback.py`
  - `tests/test_download_toast_regressions.py`

## Child DOX Index

No child DOX files.
