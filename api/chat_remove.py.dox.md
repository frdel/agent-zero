# chat_remove.py DOX

## Purpose

- Own the `chat_remove.py` API endpoint.
- This module handles chat remove requests.
- Keep this file-level DOX profile synchronized with `chat_remove.py` because this directory is intentionally flat.

## Ownership

- `chat_remove.py` owns the runtime implementation.
- `chat_remove.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `RemoveChat` (`ApiHandler`)
  - `async process(self, input: Input, request: Request) -> Output`

## Runtime Contracts

- Shared chat removal checks provider-cleanup support before scheduler cancellation, reset or local removal. Unsupported remote cleanup returns HTTP 409 and retains chat/ledger data and opt-out policy unchanged.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `RemoveChat` is an `ApiHandler`.
- `RemoveChat` defines `process(...)`.
- Observed side-effect areas: filesystem writes, filesystem deletion, settings/state persistence, scheduler state.
- Imported dependency areas include: `agent`, `helpers`, `helpers.api`, `helpers.task_scheduler`.

## Key Concepts

- Important called helpers/classes observed in the source: `scheduler.cancel_tasks_by_context`, `AgentContext.use`, `AgentContext.remove`, `persist_chat.remove_chat`, `scheduler.get_tasks_by_context_id`, `mark_dirty_all`, `context.reset`, `scheduler.reload`, `scheduler.remove_task_by_uuid`.
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
