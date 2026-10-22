# api_terminate_chat.py DOX

## Purpose

- Own the `api_terminate_chat.py` API endpoint.
- This module terminates an API-created chat context.
- Keep this file-level DOX profile synchronized with `api_terminate_chat.py` because this directory is intentionally flat.

## Ownership

- `api_terminate_chat.py` owns the runtime implementation.
- `api_terminate_chat.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ApiTerminateChat` (`ApiHandler`)
  - `requires_auth(cls) -> bool`
  - `requires_csrf(cls) -> bool`
  - `requires_api_key(cls) -> bool`
  - `get_methods(cls) -> list[str]`
  - `async process(self, input: dict, request: Request) -> dict | Response`

## Runtime Contracts

- Shared chat removal checks provider-cleanup support before context removal. Unsupported remote cleanup returns HTTP 409 and retains chat/ledger data; the API-key requirement is unchanged.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `ApiTerminateChat` is an `ApiHandler`.
- `ApiTerminateChat` defines `process(...)`.
- `ApiTerminateChat` defines `get_methods(...)`.
- `ApiTerminateChat` defines `requires_auth(...)`.
- `ApiTerminateChat` defines `requires_csrf(...)`.
- `ApiTerminateChat` defines `requires_api_key(...)`.
- Observed side-effect areas: filesystem writes, filesystem deletion, settings/state persistence.
- Imported dependency areas include: `agent`, `helpers.api`, `helpers.persist_chat`, `helpers.print_style`, `json`.

## Key Concepts

- Important called helpers/classes observed in the source: `AgentContext.use`, `AgentContext.remove`, `remove_chat`, `Response`, `PrintStyle.error`, `PrintStyle`, `json.dumps`.
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
