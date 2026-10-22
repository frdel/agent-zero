# api.py DOX

## Purpose

- Own the `api.py` helper module.
- This module defines API handler registration, request security gates, CSRF checks, and watchdog registration.
- Keep this file-level DOX profile synchronized with `api.py` because this directory is intentionally flat.

## Ownership

- `api.py` owns the runtime implementation.
- `api.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ApiHandler` (no explicit base class)
  - `requires_loopback(cls) -> bool`
  - `requires_api_key(cls) -> bool`
  - `requires_auth(cls) -> bool`
  - `get_methods(cls) -> list[str]`
  - `requires_csrf(cls) -> bool`
  - `async process(self, input: Input, request: Request) -> Output`
  - `async handle_request(self, request: Request) -> Response`
  - `use_context(self, ctxid: str, create_if_not_exists: bool=...)`
- Top-level functions:
- `requires_api_key(f)`
- `requires_loopback(f)`
- `requires_auth(f)`
- `csrf_protect(f)`
- `register_api_route(app: Flask, lock: ThreadLockType) -> None`
- `register_watchdogs()`
- Notable constants/configuration names: `CACHE_AREA`.

## Runtime Contracts

- In shared PostgreSQL mode, `use_context` checks durable ownership before any local context lookup or creation. Existing shared chats require a currently owned live turn; remote mutation endpoints must route by explicit chat ID instead of manufacturing a local shadow. Read-only recovery/document endpoints use committed database projections without this context constructor.
- Shared operation failures use fixed-safe JSON instead of the legacy traceback response, so database/provider exceptions cannot expose connection strings or private call values in HTTP output or error logs.

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- `ApiHandler` defines `process(...)`.
- `ApiHandler` defines `get_methods(...)`.
- `ApiHandler` defines `requires_auth(...)`.
- `ApiHandler` defines `requires_csrf(...)`.
- `ApiHandler` defines `requires_api_key(...)`.
- `ApiHandler` defines `requires_loopback(...)`.
- Observed side-effect areas: filesystem reads, filesystem writes, filesystem deletion, WebSocket state, plugin state, settings/state persistence, secret handling.
- Imported dependency areas include: `abc`, `flask`, `functools`, `helpers`, `helpers.errors`, `helpers.network`, `helpers.print_style`, `json`, `pathlib`, `threading`, `typing`, `werkzeug.wrappers.response`.

## Key Concepts

- Important called helpers/classes observed in the source: `wraps`, `app.add_url_rule`, `watchdog.add_watchdog`, `cls.requires_auth`, `_use_context`, `login.get_credentials_hash`, `files.get_abs_path`, `handler_cls.requires_csrf`, `handler_cls.requires_api_key`, `handler_cls.requires_auth`, `handler_cls.requires_loopback`, `cache.add`, `PrintStyle.debug`, `cache.clear`, `get_settings`, `f`, `is_loopback_address`, `Response`, `redirect`, `files.is_in_dir`.
- HTTP handlers retain built-in `api/` and explicit plugin API precedence, then fall back to standalone `usr/api/`; built-in and user roots are containment-checked, and every loaded handler keeps its declared authentication, CSRF, API-key, loopback, and method gates.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_download_toast_regressions.py`
  - `tests/test_fasta2a_client.py`
  - `tests/test_fastmcp_openapi_security.py`
  - `tests/test_host_browser_connector.py`
  - `tests/test_image_get_security.py`
  - `tests/test_model_config_api_keys.py`

## Child DOX Index

No child DOX files.
