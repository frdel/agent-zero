# Backend Helpers DOX

## Purpose

- Own shared Python framework utilities used by agents, APIs, tools, plugins, WebSockets, persistence, and runtime services.
- Keep cross-cutting behavior stable and tested.

## Ownership

- Helper modules provide reusable services; feature-specific route handlers belong in `api/`, tool behavior in `tools/`, and plugin-local logic inside plugin directories.
- Security, auth, settings, file access, plugin discovery, extension dispatch, notifications, state snapshots, scheduler, tunnel, and WebSocket primitives live here.

## Local Contracts

- Preserve public helper APIs used by core code and plugins unless all callers, docs, and tests are updated.
- Use structured parsers and serializers for YAML, JSON, paths, and URLs instead of ad hoc string handling.
- Keep path handling constrained to intended roots for user files, uploads, downloads, projects, and workdirs.
- Project metadata defaults must remain backwards-compatible; missing `include_agents_md` is treated as enabled, project instruction file content is injected with an explicit source path, and active-project AGENTS.md path-chain guidance is assembled into prompt protocol without duplicating the project root AGENTS.md.
- Do not hardcode secrets, provider keys, local absolute paths, or environment-specific values.
- `helpers.ws_limits` owns the process-start WebSocket payload ceiling shared by
  transport configuration and connector capability negotiation. Protocol
  senders pass the negotiated peer ceiling to `WsManager.emit_to`, which owns
  exact serialized-envelope enforcement before buffering or dispatch. The
  namespace dispatcher also asks the manager to constrain the final merged
  acknowledgement against the limit stored on that live connection. That stored
  ceiling is authoritative for direct emits and broadcasts from every handler,
  not only connector-plugin call sites.
- Use `RepairableException` for errors an agent may be able to fix.
- This directory is a file-documented DOX profile: every direct `*.py` helper module must have a same-directory `*.py.dox.md` file named by appending `.dox.md` to the full Python filename.
- The `*.py.dox.md` file owns helper purpose, public classes/functions, cross-module contracts, persistence or side effects, path/security assumptions, important dependencies, and verification guidance.
- When a helper module is added, removed, renamed, or behaviorally changed, update its matching `*.py.dox.md` in the same change.
- Do not leave stale file-level DOX after helper deletion or rename.

## Work Guidance

- Prefer cohesive helper modules over adding unrelated utilities to large files.
- Keep imports acyclic where possible; defer imports inside functions only when needed to avoid startup cycles.
- For changes touching auth, CSRF, files, plugins, tunnels, WebSockets, or model calls, read the caller and tests before editing.
- During the DOX pass, verify that every direct `*.py` file has a matching `*.py.dox.md` and that changed helper behavior is described there.

## Verification

- Run targeted tests for changed helper modules.
- Run security regression tests for auth, CSRF, filesystem, WebSocket, tunnel, upload, or image-serving changes.
- Check file-level documentation coverage with a script or shell loop that verifies each `helpers/*.py` has a matching `helpers/*.py.dox.md`.

## Child DOX Index

| Child | Scope |
| --- | --- |
| [durable/AGENTS.md](durable/AGENTS.md) | SQLite/PostgreSQL recovery storage, session-fenced workers, durable commands, private codecs, shared payload/retention custody, scheduler/child adapters and replay audits. |
