# Tests DOX

## Purpose

- Own pytest regression, security, integration, and contract tests.
- Keep tests focused on behavior that should remain stable across framework changes.

## Ownership

- Test files live directly under `tests/` and are named for the behavior or subsystem they cover.
- Shared fixtures should be added only when multiple tests need them.
- Runtime artifacts created during tests should use pytest temporary directories or existing isolated test helpers.

## Local Contracts

- Tests must not require real API keys, network-only services, private user data, or local `usr/` runtime state. Manual provider demos must guard model creation and requests behind their executable entry point so collection never runs them.
- Keep tests deterministic and isolated from existing chats, uploads, downloads, plugin state, and settings.
- Prefer exercising public helper/API contracts over fragile implementation details when practical.
- Unit tests for an extension body instantiate the owning extension directly; discovery tests isolate configuration and caches. Optional network transports use scoped collaborator fakes without importing their SDKs, restoring both module and package bindings after the test.
- Security regression tests should assert the protected behavior directly.
- Launcher gateway tests must cover feature negotiation, authenticated and
  CSRF-protected control, acknowledgement timeout, identity lifecycle,
  context-bound CLI routing precedence, duplicate/multiple-host behavior,
  scope-driven availability, and emergency disconnect without a live host.

## Work Guidance

- Add focused tests near the affected subsystem's existing tests.
- Use descriptive test names that state the regression or contract.
- Avoid broad sleeps or real-time dependencies; use monkeypatching or controlled clocks where possible.

## Verification

- Run `pytest` for broad changes.
- Run `pytest tests/test_name.py` for narrow changes and mention any broader test gaps at closeout.
- Run `pytest tests/test_litellm_sdk.py -q` for LiteLLM/OpenAI upgrades. Its loopback provider exercises the installed SDK's sync/async calls, streaming, tool/state preservation, fallback, embeddings, and Anthropic cache markers without real keys or external requests.
- Run `pytest tests/test_framework_dependencies.py -q` for dependency migration changes; verify stale self-update environments, process restart, and already-current image installs.

## Child DOX Index

No child DOX files.
