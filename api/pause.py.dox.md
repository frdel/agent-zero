# pause.py DOX

## Purpose

- Own the `pause.py` API endpoint.
- This module handles pause API requests.
- Keep this file-level DOX profile synchronized with `pause.py` because this directory is intentionally flat.

## Ownership

- `pause.py` owns the runtime implementation.
- `pause.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `Pause` (`ApiHandler`)
  - `async process(self, input: dict, request: Request) -> dict | Response`

## Runtime Contracts

- Shared mode routes an explicit context ID to `pause_remote` before constructing a local context. The response is a queued command receipt and requested pause value; it does not claim the execution owner is quiescent. A supplied request ID remains stable; older callers receive a generated identity.

- With a durable run, pause/unpause commits the checkpoint control state before reporting success. Unpausing a restored supported run goes through the sole dispatcher; it never creates a second driver. Off-mode behavior is unchanged.

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `Pause` is an `ApiHandler`.
- `Pause` defines `process(...)`.
- Imported dependency areas include: `helpers.api`.

## Key Concepts

- Important called helpers/classes observed in the source: `self.use_context`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Unpause uses the current run's restore selection; an attention hold must be resolved through Recovery & documents. Pausing an attention row cannot replace its checkpoint watermark or bypass review.
- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Related tests observed by source search:
  - `tests/test_multi_tab_isolation.py`
  - `tests/test_snapshot_schema_v1.py`

## Child DOX Index

No child DOX files.
