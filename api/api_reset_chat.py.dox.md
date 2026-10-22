# api_reset_chat.py DOX

## Purpose

- Own the `api_reset_chat.py` API endpoint.
- This module resets an API-created chat context.
- Keep this file-level DOX profile synchronized with `api_reset_chat.py` because this directory is intentionally flat.

## Ownership

- `api_reset_chat.py` owns the runtime implementation.
- `api_reset_chat.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ApiResetChat` (`ApiHandler`)
  - `requires_auth(cls) -> bool`
  - `requires_csrf(cls) -> bool`
  - `requires_api_key(cls) -> bool`
  - `get_methods(cls) -> list[str]`
  - `async process(self, input: dict, request: Request) -> dict | Response`

## Runtime Contracts

- Shared mode requires a stable `request_id` (HTTP 409 with no effects when absent) and fences the named context through the database coordinator's atomic control receipt without looking up or constructing a local chat. Accepted retries cannot reset newer work. The existing API-key protection remains required; workers discard the previous generation asynchronously.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `ApiResetChat` is an `ApiHandler`.
- `ApiResetChat` defines `process(...)`.
- `ApiResetChat` defines `get_methods(...)`.
- `ApiResetChat` defines `requires_auth(...)`.
- `ApiResetChat` defines `requires_csrf(...)`.
- `ApiResetChat` defines `requires_api_key(...)`.
- Observed side-effect areas: filesystem writes, filesystem deletion, settings/state persistence.
- Imported dependency areas include: `agent`, `helpers`, `helpers.api`, `helpers.print_style`, `json`.

## Key Concepts

- Important called helpers/classes observed in the source: `AgentContext.use`, `context.reset`, `persist_chat.save_tmp_chat`, `persist_chat.remove_msg_files`, `Response`, `PrintStyle.error`, `PrintStyle`, `json.dumps`.
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
