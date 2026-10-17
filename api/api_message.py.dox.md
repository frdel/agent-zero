# api_message.py DOX

## Purpose

- Own the `api_message.py` API endpoint.
- This module accepts external API messages and dispatches them into Agent Zero chat processing.
- Keep this file-level DOX profile synchronized with `api_message.py` because this directory is intentionally flat.

## Ownership

- `api_message.py` owns the runtime implementation.
- `api_message.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ApiMessage` (`ApiHandler`)
  - `requires_auth(cls) -> bool`
  - `requires_csrf(cls) -> bool`
  - `requires_api_key(cls) -> bool`
  - `async process(self, input: dict, request: Request) -> dict | Response`

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `ApiMessage` is an `ApiHandler`.
- `ApiMessage` defines `process(...)`.
- `ApiMessage` defines `requires_auth(...)`.
- `ApiMessage` defines `requires_csrf(...)`.
- `ApiMessage` defines `requires_api_key(...)`.
- Observed side-effect areas: filesystem reads, filesystem writes, settings/state persistence, secret handling, scheduler state.
- New-context creation with an explicit `agent_profile` records the `agent_profile_manually_set` context data flag (before project activation triggers reconciliation) so manual selections are protected from project-default reconciliation.
- Imported dependency areas include: `agent`, `base64`, `datetime`, `helpers`, `helpers.api`, `helpers.print_style`, `helpers.projects`, `helpers.security`, `initialize`, `os`, `uuid`.

## Key Concepts

- Important called helpers/classes observed in the source: `context.set_data`, `datetime.now`, `Response`, `files.get_abs_path`, `os.makedirs`, `AgentContext.use`, `context.get_data`, `initialize_agent`, `AgentContext`, `context.log.log`, `context.communicate`, `ValueError`, `uuid.uuid4`, `UserMessage`, `task.result`, `PrintStyle.error`, `safe_filename`, `base64.b64decode`, `os.path.join`, `activate_project`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Related tests observed by source search:
  - `tests/test_api_chat_lifetime.py`

## Child DOX Index

No child DOX files.
