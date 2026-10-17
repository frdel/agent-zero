# response.py DOX

## Purpose

- Own the `response.py` agent tool.
- This module emits the final or intermediate agent response to the user.
- Keep this file-level DOX profile synchronized with `response.py` because this directory is intentionally flat.

## Ownership

- `response.py` owns the runtime implementation.
- `response.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `ResponseTool` (`Tool`)
  - `async execute(self, **kwargs)`
  - `async before_execution(self, **kwargs)`
  - `async after_execution(self, response, **kwargs)`
- Top-level functions:
- `_response_context_id(agent) -> str`

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `ResponseTool` is a `Tool`.
- `ResponseTool` defines `execute(...)`.
- `ResponseTool` requires a non-empty top-level string `text` or legacy `message`
  argument, preferring `text` and falling back to `message` when `text` is blank.
  Invalid arguments raise `RepairableException` so the agent can surface a correction
  warning and retry rather than crash.
- Imported dependency areas include: `helpers`, `helpers.errors`, `helpers.tool`.
- `after_execution` marks the live response log finished and rewrites local `img://` / `/api/image_get?path=` image refs onto unique chat-scoped snapshots so later filename reuse cannot overwrite earlier bubbles.

## Key Concepts

- Important called helpers/classes observed in the source: `Response`, `chat_media.snapshot_image_refs`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- Related tests observed by source search:
  - `tests/chunk_parser_test.py`
  - `tests/rate_limiter_test.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_chat_compaction.py`
  - `tests/test_dirty_json.py`
  - `tests/test_download_toast_regressions.py`
  - `tests/test_fasta2a_client.py`
  - `tests/test_fastmcp_openapi_security.py`
  - `tests/test_chat_media_response_snapshots.py`
  - `tests/test_response_tool_validation.py`
  - `tests/test_plain_response_logging.py`

## Child DOX Index

No child DOX files.
