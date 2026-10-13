# AnySearch Plugin DOX

## Purpose

- Own the optional AnySearch web search integration: general search,
  vertical-domain search, client-side batch search, and URL extraction.
- Provide this as a separate, opt-in tool without changing the default
  `search_engine` (SearXNG) tool or its behavior.

## Ownership

- `.toggle-0` ships the plugin disabled by default (Agent Zero plugins are
  active by default unless a `.toggle-0` marker is present — see
  `_infection_check` for the same pattern); a user opts in via the Plugins
  panel, which writes its own override under `usr/plugins/_anysearch/`.
- `helpers/anysearch_client.py` owns the AnySearch HTTP client (auth,
  timeouts, argument validation, request/response shape, `tag`/`params`
  resolution, per-item-isolated batch fan-out, error diagnostics).
- `tools/anysearch.py` owns the agent-facing `anysearch` tool: action
  dispatch, config/API-key resolution, and output formatting.
- `prompts/agent.system.tool.anysearch.md` owns the tool contract shown to
  the agent; keep it synchronized with tool argument names and behavior.
- `default_config.yaml` and `plugin.yaml` own non-secret defaults and
  plugin metadata.
- `tests/` owns unit coverage for the client and tool, with the AnySearch
  API mocked.

## Local Contracts

- Read the AnySearch API key only via `models.get_api_key("anysearch")`;
  never make it a tool argument or a plugin setting, never intentionally put
  it into exceptions or tool output, and keep redacting direct occurrences of
  it (bare and `Bearer <key>`) from remote/network error text.
- Remote error text always passes through `redact_credentials()` before it
  enters an `AnySearchError`; a remote message carrying service-generated
  credentials (HTTP 402 anonymous-quota flow or an `auto_registered`
  payload) is replaced entirely by `GENERATED_CREDENTIALS_MESSAGE` and those
  credentials are never persisted.
- Successful responses require an integer business `code` of 0 and pass the
  per-endpoint validators for the official REST contract (search `results`
  list with string `title`/`url`; sub-domain entries with a `sub_domains`
  list and complete parameter definitions; extract `url`/`title`/`content`);
  malformed payloads raise (with `request_id`) instead of rendering as empty
  results.
- Anonymous access must keep working with no API key configured, and must
  not send an `Authorization` header; blank/whitespace-only keys and the
  `"None"` placeholder are normalized to no key (`normalize_api_key()`).
- Do not modify `tools/search_engine.py` or `helpers/searxng.py` from this
  plugin; AnySearch is additive, not a replacement.
- Every AnySearch HTTP call must have a positive, finite timeout.
- Validate all tool arguments locally before any network call: `query` a
  non-empty string; `tag`/`sub_domain`/`domain` absent or non-empty strings;
  `params`/`sub_domain_params` objects (conflicting values rejected);
  `zone` `cn`/`intl`; `language` a string; `max_results` (request and
  plugin config) a strict integer clamped to 1-10; `action` a known string
  (omitted/`null` = `search`); extract `url` and config `base_url` absolute
  `http(s)` URLs with a host and no embedded credentials. Extract targets
  additionally must be public (`validate_extract_target()`: no
  `localhost`/`*.localhost` or non-global IP literals, no DNS resolution)
  and fit the 16 KiB request-body limit; `base_url` is exempt from the
  public-target rule, but with an API key it must be `https://` unless the
  host is loopback (`localhost`, 127.0.0.0/8, `::1`). A malformed routing
  argument must never degrade into a general search.
- `ACTION_ARGS` in `tools/anysearch.py` is the per-action argument
  allow-list (search fields; `queries`; `domains`/`domain`; `url`). Any other
  argument — including one valid for another action, or an unknown key — is
  rejected before config, client, or network work; a known field sent as
  `null` counts as absent, and the framework's `method` alias is accepted
  only when it equals the action. Keep it in sync with the native schema.
- `params`/`sub_domain_params` and `domains`/`domain` are alias pairs: both
  present must be exactly equal (params) or is rejected (domains); never
  silently choose one.
- `redact_configured_key()` must run on every successful payload before
  formatting; remote output keeps its untrusted-data notice, `_line()`
  escaping for display text, and `_exact()` single-line rendering for
  identifiers and metadata (never dropping null/empty values).
- The prompt's `Input schema for tool_args:` JSON is the native Responses
  schema; keep it synchronized with tool arguments and free of `{{`.
- `batch_search` is capped at `MAX_BATCH_SIZE` (5, a fixed protocol
  constant). Only batch-level problems (not a list, empty, over the cap)
  fail the whole call; every item is otherwise isolated — a malformed item
  gets its own error entry with zero network requests, a backend failure
  never aborts siblings, and results keep input order.
- `resolve_tag()` never concatenates `domain` + `.` + `sub_domain` —
  `sub_domain` (like `GET /v1/sub-domains` results) already arrives fully
  qualified (e.g. `finance.quote`); `domain` is a validation hint only.
- `_format_sub_domains()` must render every parameter's required flag and
  description, order parameters by `sort_order` (used for ordering, not
  printed), and keep every additional returned metadata field (rendered
  generically, never truncated, empty/null values included), so constraints
  and new upstream fields are never silently dropped.
- `max_results` precedence for both `search` and every `batch_search` item
  goes through `tools/anysearch.py`'s single `_resolve_max_results()`
  helper: an explicit value wins; a missing key or explicit `null` uses the
  plugin's configured default.
- No new third-party dependency: reuse `aiohttp`, already used by
  `helpers/searxng.py`.

## Work Guidance

- When AnySearch's documented API changes, update
  `helpers/anysearch_client.py` first, then `tools/anysearch.py`
  formatting, then the prompt contract; see `MAINTENANCE.md` for the full
  procedure and the current documented endpoint surface.
- Keep tool output concise and model-readable, matching the style of
  `tools/search_engine.py`'s formatted results.
- Extracted page content is untrusted external data; keep the safety
  notice in `tools/anysearch.py`'s `extract` formatting.

## Verification

- Run `pytest plugins/_anysearch/tests` after any change here.
- Run the broader `pytest` suite before proposing a PR; confirm
  `tools/search_engine.py` behavior (SearXNG default path) is unaffected.
- Tests must not depend on live network access; mock
  `AnySearchClient`/`aiohttp` calls for deterministic CI.

## Child DOX Index

No child DOX files.
