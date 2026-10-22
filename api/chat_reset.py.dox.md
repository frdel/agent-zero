# chat_reset.py DOX

## Purpose

- Own the `chat_reset.py` API endpoint.
- This module handles chat reset requests.
- Keep this file-level DOX profile synchronized with `chat_reset.py` because this directory is intentionally flat.

## Ownership

- `chat_reset.py` owns the runtime implementation.
- `chat_reset.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `Reset` (`ApiHandler`)
  - `async process(self, input: Input, request: Request) -> Output`

## Runtime Contracts

- Shared mode requires a stable `request_id` (HTTP 409 with no effects when absent) and fences the context/descendant generation through the database coordinator's atomic control receipt before any local context lookup. Repeating an accepted request cannot reset newer work. It does not reset or save a requester-side shadow or remove another host's message files.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `Reset` is an `ApiHandler`.
- `Reset` defines `process(...)`.
- Observed side-effect areas: filesystem writes, filesystem deletion, settings/state persistence, scheduler state.
- Imported dependency areas include: `helpers`, `helpers.api`, `helpers.task_scheduler`.

## Key Concepts

- Important called helpers/classes observed in the source: `TaskScheduler.get.cancel_tasks_by_context`, `self.use_context`, `context.reset`, `persist_chat.save_tmp_chat`, `persist_chat.remove_msg_files`, `mark_dirty_all`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- No direct test reference was found by name search; choose the nearest behavioral test or perform a focused smoke check.

## Child DOX Index

No child DOX files.
