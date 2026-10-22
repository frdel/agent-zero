# API Handlers DOX

## Purpose

- Own backend HTTP API handlers and WebSocket handler entry points.
- Keep route-level behavior, authentication, CSRF, input parsing, and response shapes explicit.

## Ownership

- Files in this directory are discovered by the route registration layer in `helpers/api.py` and WebSocket registration code.
- Scheduler CRUD endpoints live in `plugins/_scheduler/api/` and resolve through the plugin API route format; `scheduler_tick.py` stays here with the scheduling engine.
- `ws_*.py` files define WebSocket namespaces or handlers through `helpers.ws.WsHandler`.
- Plugin-provided API handlers belong inside plugin `api/` folders and follow the same base contracts.

## Local Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`.
- Implement `async def process(self, input: dict, request: Request) -> dict | Response`.
- Override `get_methods()`, `requires_auth()`, `requires_csrf()`, `requires_api_key()`, or `requires_loopback()` only when the endpoint contract requires it.
- Keep CSRF and authentication protections intact for browser-facing state-changing endpoints.
- WebSocket handlers must derive from `helpers.ws.WsHandler` and validate event data before using it.
- Do not return secrets, raw environment values, private files, or unfiltered exception details to clients.
- Upload bodies are streamed to same-directory `.partial-*` files, hashed and
  fsynced, then atomically replaced; retain the legacy filename response while
  adding ordered size/SHA-256 receipts. Download responses remain streamed and
  include Content-Length plus `X-Content-SHA256` for atomic client verification.
- This directory is a file-documented DOX profile: every direct `*.py` endpoint or WebSocket module must have a same-directory `*.py.dox.md` file named by appending `.dox.md` to the full Python filename.
- The `*.py.dox.md` file owns endpoint purpose, request/response concepts, auth/CSRF/API-key/loopback assumptions, side effects, important helper dependencies, and verification guidance.
- When a Python endpoint is added, removed, renamed, or behaviorally changed, update its matching `*.py.dox.md` in the same change.
- Do not leave stale file-level DOX after endpoint deletion or rename.

## Work Guidance

- Use helpers for shared behavior instead of duplicating persistence, auth, file, project, plugin, or notification logic in endpoints.
- Keep request and response payloads stable; update frontend callers and tests together when payloads change.
- Prefer `Response` for files, redirects, status codes, and plain-text errors; return dictionaries for JSON success payloads.
- During the DOX pass, verify that every direct `*.py` file has a matching `*.py.dox.md` and that changed endpoint behavior is described there.

## Verification

- Run targeted `pytest tests/test_*api*.py`, endpoint-specific tests, or WebSocket tests after changing handler behavior.
- For auth, CSRF, upload/download, tunnel, or file endpoints, run the nearest security regression tests.
- Check file-level documentation coverage with a script or shell loop that verifies each `api/*.py` has a matching `api/*.py.dox.md`.

## Child DOX Index

No child DOX files.
