# Search Engine Plugin DOX

## Purpose

- Own the `search_engine` tool for live web search via the local SearXNG instance.

## Ownership

- `tools/search_engine.py` owns query execution, result formatting, and error handling.
- `extensions/webui/get_tool_message_handler/` owns the tool message presentation moved from core `webui/js/messages.js`.
- `prompts/` owns the tool prompt.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Search runs through `helpers.searxng.search`, which proxies to the SearXNG URL inside the development runtime via `runtime.call_development_function`.
- Result cap is `SEARCH_ENGINE_RESULTS = 10`; exceptions flow through `helpers.errors.handle_error` and return a failed-search message instead of raising.
- The WebUI handler registers only for `tool_name === "search_engine"` and reuses `drawMessageToolSimple` with code `WEB`.

## Verification

- Import the tool in the framework runtime and run the tool contract and WebUI plugin process-type tests after changes.

## Child DOX Index

No child DOX files.
