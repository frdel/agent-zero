# Search Engine Plugin DOX

## Purpose

- Own the `search_engine` tool for live web search via the local SearXNG instance.

## Ownership

- `tools/search_engine.py` owns query execution, result formatting, and error handling.
- `extensions/webui/get_message_handler/` owns the tool message presentation moved from core `webui/js/messages.js`.
- `extensions/webui/get_process_step_types/` owns the `search_engine` process step type registration.
- `prompts/` owns the tool prompt.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Search runs through `helpers.searxng.search`, which proxies to the SearXNG URL inside the development runtime via `runtime.call_development_function`.
- Result cap is `SEARCH_ENGINE_RESULTS = 10`; exceptions flow through `helpers.errors.handle_error` and return a failed-search message instead of raising.
- The tool logs its message as type `search_engine` with an `icon://search Searching: <query>` headline. The WebUI message handler registers only for that type and reuses `drawMessageToolSimple` with code `SRC`, styled by the web access indigo styles shared with the browser badge that `extensions/webui/page-head/` loads; `extensions/webui/get_process_step_types/` registers the type.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with the tool prompt and the shared SearXNG helper contract.
- Respect intervention flow before and after remote searches.

## Verification

- Import the tool in the framework runtime and run the tool contract and WebUI plugin process-type tests after changes.
- Run `tests/test_search_engine_tool.py` for the tool formatting and execution regression tests.

## Child DOX Index

No child DOX files.
