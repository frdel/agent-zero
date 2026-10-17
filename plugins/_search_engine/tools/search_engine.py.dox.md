# search_engine.py DOX

## Purpose

- Own the `search_engine.py` agent tool.
- This module runs web search through the configured search helper.
- Keep this file-level DOX profile synchronized with `search_engine.py` because this directory is intentionally flat.

## Ownership

- `search_engine.py` owns the runtime implementation.
- `search_engine.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `SearchEngine` (`Tool`)
  - `async execute(self, query=..., **kwargs)`
  - `async searxng_search(self, question)`
  - `format_result_searxng(self, result, source)`
  - `get_log_object(self)`
  - `get_heading(self)`
- Notable constants/configuration names: `SEARCH_ENGINE_RESULTS`.

## Runtime Contracts

- Tool modules must define `helpers.tool.Tool` subclasses and return `helpers.tool.Response` from `execute(...)`.
- Update this file whenever tool arguments, output shape, `break_loop` behavior, intervention handling, prompt instructions, or side effects change.
- `SearchEngine` is a `Tool`.
- `SearchEngine` defines `execute(...)`.
- Imported dependency areas include: `helpers.errors`, `helpers.searxng`, `helpers.strings`, `helpers.tool`, `uuid`.

## Key Concepts

- Important called helpers/classes observed in the source: `Response`, `self.format_result_searxng`, `join.strip`, `self.searxng_search`, `self.agent.handle_intervention`, `searxng`, `handle_error`, `join`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with prompt tool instructions and skill guidance.
- Respect intervention flow for long-running, external, or user-visible operations.

## Verification

- Run `tests/test_search_engine_tool.py` for the result formatting and search execution regression tests.

## Child DOX Index

No child DOX files.
