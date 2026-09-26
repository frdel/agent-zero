# Python Function Extensions DOX

## Purpose

- Own implicit `@extensible` backend hook implementations.
- Preserve nested module, class/function, method, and `start`/`end` extension layout.

## Ownership

- Each nested path mirrors a Python module and qualname segment.
- Leaf `start/` and `end/` directories own ordered extension files for that extensible function point.

## Local Contracts

- The unusable-response counter also counts static leaked-call and truncated-call warnings once per iteration; variable diagnostics remain outside warning text.

- Do not flatten nested qualname paths into retired legacy folder names.
- Extension functions must match the implicit hook's supplied arguments.
- Preserve ordering prefixes where exception handling, watchdog registration, or cleanup depends on them.
- Hooks that mirror persisted AI responses into UI logs must reuse existing stream log items and avoid duplicating live response-tool logs. Native-call commentary must not be finalized as a plain response; canonical calls keep their tool-step log ownership.
- The `AgentContext.run_task/end` hook attaches integration callbacks to the returned `DeferredTask`; keep terminal side effects out of `agent.py`.
- The `Agent.monologue/end` hook reconciles successful main-agent continuations with errored scheduler tasks using the persisted task UUID (or the context ID for legacy dedicated chats). Use a checked scheduler update so disabled, removed, reassigned, and scheduler-managed running tasks are preserved; do not advance planned launch times again.
- Recovery-loop circuit breakers must stop at the General Settings limit and render their user-visible cost warning from a core framework prompt.
- Prompt settings snapshots must be task-local, accessed through `get_settings_for_prompt()`, and end with the matching `Agent.prepare_prompt` call, including exceptional exits.

## Work Guidance

- Keep implicit hook extensions narrow and colocated with the exact function point they extend.

## Verification

- Run targeted tests for the affected function point after changes.

## Child DOX Index

No child DOX files.
