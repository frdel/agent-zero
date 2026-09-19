# wait.py DOX

## Purpose

- Own the `wait.py` agent tool.
- This module lets the agent wait for a managed duration while respecting intervention flow.
- Keep this file-level DOX profile synchronized with `wait.py` because this directory is intentionally flat.

## Ownership

- `wait.py` owns the runtime implementation.
- `wait.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `WaitTool` (`Tool`)
  - `async execute(self, **kwargs) -> Response`
  - `get_log_object(self)`
  - `get_heading(self, text: str=..., done: bool=...)`

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `WaitTool` is a `Tool`.
- `WaitTool` defines `execute(...)`.
- Observed side-effect areas: settings/state persistence.
- Imported dependency areas include: `asyncio`, `datetime`, `helpers.localization`, `helpers.print_style`, `helpers.tool`, `helpers.wait`.

## Key Concepts

- Important called helpers/classes observed in the source: `Localization.get.now`, `PrintStyle.info`, `self.agent.read_prompt`, `Response`, `self.agent.context.log.log`, `self.agent.handle_intervention`, `timedelta`, `managed_wait`, `Localization.get.localtime_str_to_utc_dt`, `wait_duration.total_seconds`, `Localization.get.serialize_datetime`, `self.get_heading`, `ValueError`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run targeted tool and prompt-contract tests for changed behavior; smoke-test agent execution when no focused test exists.
- Related tests observed by source search:
  - `tests/email_parser_test.py`
  - `tests/rate_limiter_test.py`
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_chat_compaction.py`
  - `tests/test_default_prompt_budget.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_download_toast_regressions.py`

## Child DOX Index

No child DOX files.
