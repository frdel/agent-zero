# message_async.py DOX

## Purpose

- Own the `message_async.py` API endpoint.
- This module submits a user message for asynchronous agent processing.
- Keep this file-level DOX profile synchronized with `message_async.py` because this directory is intentionally flat.

## Ownership

- `message_async.py` owns the runtime implementation.
- `message_async.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `MessageAsync` (`Message`)
  - `async respond(self, task: DeferredTask, context: AgentContext)`

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- When `communicate` rejects the message (`model_not_configured`), the response payload reports `"model_not_configured": true` with the context id instead of the acknowledgment payload.
- Observed side-effect areas: scheduler state.
- Imported dependency areas include: `agent`, `api.message`, `helpers.defer`.

## Key Concepts

- This module is primarily declarative or delegates behavior through classes/imported objects.
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
