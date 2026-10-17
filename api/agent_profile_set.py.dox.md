# agent_profile_set.py DOX

## Purpose

- Own the `agent_profile_set.py` API endpoint.
- This module sets the active agent profile for a chat context and returns profile label metadata.
- Keep this file-level DOX profile synchronized with `agent_profile_set.py` because this directory is intentionally flat.

## Ownership

- `agent_profile_set.py` owns the runtime implementation.
- `agent_profile_set.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SetAgentProfile` (`ApiHandler`)
  - `async process(self, input: dict, request: Request) -> dict | Response`

## Runtime Contracts

- HTTP handlers must derive from `helpers.api.ApiHandler`; WebSocket handlers must derive from `helpers.ws.WsHandler`.
- Update this file whenever request payloads, authentication or CSRF requirements, response shapes, route side effects, or WebSocket event contracts change.
- `SetAgentProfile` is an `ApiHandler`.
- `SetAgentProfile` defines `process(...)`.
- Observed side-effect areas: filesystem writes, settings/state persistence.
- Switching a chat profile updates the context and top-level agent profile only; existing subordinate agents keep their own profile configs.
- Explicit profile selection sets the `agent_profile_manually_set` context data flag (persisted via `save_tmp_chat` because non-underscore `context.data` keys are serialized); `helpers/projects.py` `reconcile_agent_profile(...)` skips project-default-agent overrides for flagged contexts, so explicit selections survive reconcile sweeps.
- A profile can be selected only when it is available in the chat's active
  project scope; profiles owned by other projects are not valid candidates.
- Imported dependency areas include: `agent`, `helpers`, `helpers.api`, `helpers.persist_chat`, `helpers.state_monitor_integration`.

## Key Concepts

- Important called helpers/classes observed in the source: `str.strip`, `context.is_running`, `initialize_agent`, `context.agent0.config`, `save_tmp_chat`, `mark_dirty_for_context`, `projects.get_context_project_name`, `subagents.get_available_agents_dict`, `Response`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve authentication, CSRF, loopback, and API-key checks unless the endpoint contract explicitly changes.
- Update frontend callers, plugin callers, and tests together when payload shape changes.
- Use `helpers.api.Response` for non-JSON responses, files, redirects, or status-specific replies.

## Verification

- Run endpoint-specific or API/WebSocket tests for changed behavior; smoke-test browser callers when no focused test exists.
- Related tests observed by source search:
  - `tests/test_subagent_profiles.py`

## Child DOX Index

No child DOX files.
