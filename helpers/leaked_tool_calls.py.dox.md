# leaked_tool_calls.py DOX

## Purpose

- Recover one complete, standalone leaked text tool call without repairing or guessing argument values.
- Keep permissive canonical parsing in `extract_tools.py` unchanged.

## Ownership

- `salvage_leaked_tool_call(response, offered_tools=None, *, tool_name_map=None)` returns immutable `SalvageResult(request, status, detail)`.
- Status is `clean`, `salvaged`, `leaked_unsalvageable`, or `truncated`; `detail` is a content-free reason code.
- The core `_05_leaked_tool_call` result hook owns recovery and retry side effects, using the Responses turn map or lazily resolving the current Chat Completions prompt/MCP surface; Context Doctor uses classification only to avoid undoing the decision.

## Local Contracts

- Accept standalone `<tool_call>` JSON objects/single-item arrays, `<function=...>` parameter envelopes (also inside `<tool_call>`), and native `name` plus `arguments`/`parameters` objects. JSON-encoded arguments must decode completely to an object.
- Require explicit available tool names from the caller. Missing or empty availability cannot authorize recovery. Map provider aliases before checking normalized names; retain existing action/method normalization.
- This validates envelope shape and offered names, not each tool's argument schema. Normal dispatch retains argument validation, policy gates, hooks, and `break_loop` behavior.
- Reject multiple calls, surrounding prose, duplicate keys/parameters, conflicting envelope fields, unsupported formats, invalid JSON, and nonfinite JSON numbers. Never select the first or most complete call from a group.
- Never repair truncated requests. JSON inside string values is string-aware, and canonical A0 requests retain their existing behavior.
- Exclude fenced/inline examples from recovery and mark them `clean` with `quoted_tool_syntax` so Context Doctor cannot execute their contents. Do not strip code fences inside argument values.
- XML parameter values are preserved verbatim; only whitespace-free, complete JSON tokens are coerced. Ambiguous nested tool markup is rejected.
- No filesystem, network, logging, settings, or persistence side effects; diagnostics contain no model arguments. No new dependencies.

## Work Guidance

- Extend recognized formats only with rejection and quoted-example tests.
- Keep strict recovery independent of the existing dirty parser; do not share scanners at the cost of changing canonical/streaming behavior.
- Streaming detection, token-budget changes, and bare `toolname {args}` shorthand are out of scope.

## Verification

- Run `pytest tests/test_leaked_tool_calls.py tests/test_leaked_tool_call_integration.py tests/test_unusable_response_loop.py plugins/_context_doctor/tests` in the framework runtime.
- Retest normalization, native Responses dispatch, tool policy, and streaming early-stop when changing integration.

## Child DOX Index

No child DOX files.
