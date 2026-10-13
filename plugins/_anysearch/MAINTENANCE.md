# AnySearch Plugin — Maintenance

## Ownership

- `helpers/anysearch_client.py` owns the HTTP client: argument validation,
  request/response handling, auth header construction, timeouts, error
  diagnostics, and the client-side `batch_search` fan-out.
- `tools/anysearch.py` owns the agent-facing tool: action dispatch
  (`search`, `batch_search`, `get_sub_domains`, `extract`), plugin config +
  API key resolution, and model-readable output formatting.
- `prompts/agent.system.tool.anysearch.md` owns the tool contract shown to
  the agent; keep it synchronized with `tools/anysearch.py` argument names
  and behavior.
- `default_config.yaml` owns non-secret defaults (`base_url`, `timeout`,
  `max_results`). `batch_search`'s 5-query limit is a fixed protocol
  constant (`MAX_BATCH_SIZE` in `helpers/anysearch_client.py`), not a
  configurable setting.
- `tests/` owns unit coverage with the AnySearch API mocked; no test in this
  suite depends on network access.

## External API surface this plugin depends on

Sources: <https://www.anysearch.com/docs> and the first-party reference
client `anysearch-ai/anysearch-skill` (`SKILL.md`,
`scripts/shared/doc_spec.md`, `scripts/anysearch_cli.py`). Agent Zero uses
the REST endpoints directly, not the AnySearch MCP server.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/v1/search` | POST | general + vertical-domain search (`query`, `max_results` 1-10, `tag`, `params`, `zone`, `language`) |
| `/v1/sub-domains` | GET | vertical-domain/sub-domain + parameter discovery (repeated `domain` query param, up to 5) |
| `/v1/extract` | POST | full-page content extraction (`url`); `content` may be cleaned HTML, plain text, JSON, or Markdown depending on the source |

The available domains and sub-domains are discovered at runtime through
`/v1/sub-domains`; the plugin does not hard-code a catalog.

**Batch.** There is no server-side batch endpoint; `batch_search` sends one
independent `/v1/search` per item (1-5 items, concurrently), like the
reference client. Batch-level errors (not a list, empty, more than 5) fail
the call; everything else is per item. A malformed item gets an error entry
without a network request, a backend failure affects only its own item, and
output keeps input order.

**Vertical-domain routing (`tag`).** `/v1/search`'s `tag` field is the single
REST-native routing key: a fully-qualified key, e.g. `finance.quote`.
`GET /v1/sub-domains`'s `sub_domain` values are already fully qualified —
never prefix them with `domain`. `resolve_tag()` treats `sub_domain` as a
`tag` alias (both given must match) and never concatenates it with `domain`.
`domain` is only a local validation hint (it must match the tag's prefix) and
is never sent over the wire. Routing fields must be absent or non-empty
strings; any other value is rejected so a vertical search never silently
becomes a general one. `params` and its alias `sub_domain_params` must be
objects when present (`null` = absent, `{}` = present but empty); when both
are present they must be exactly equal (`{}` + non-empty is a conflict),
otherwise the call is rejected before any request — one alias is never
silently chosen. For `get_sub_domains`, `domains` is the documented field and
singular `domain` a compatibility alias; sending both is rejected.

**Sub-domain metadata.** `_format_sub_domains()` renders each parameter's
required flag and description, uses `sort_order` only for deterministic
ordering (it is not printed), and then renders every additional key the API
returns (allowed values, options, examples, defaults, formats, ...,
including empty/null values) generically and deterministically and never
truncates values, so complete constraints (e.g.
long enum/options lists) and new upstream metadata always reach the agent.
Keep it generic; do not switch to a fixed allow-list of known keys.

**Extract.** This plugin uses the REST endpoint, whose `data.content` is
cleaned HTML, plain text, JSON, or Markdown depending on the source (it is not
always Markdown; that is the MCP tool's presentation). The documented supported
inputs are HTML/XHTML, plain text, JSON, and Markdown; binary formats (PDF, office documents, images,
audio/video, archives) are unsupported. HTML/plain-text output may be
truncated at 50,000 characters and oversized JSON/Markdown returns an error
(both server-side). The official contract takes a public absolute
`http(s)` URL in a strict JSON body of at most 16 KiB. `validate_extract_target()`
enforces this locally, before any network call: a host is required; embedded
credentials (`user@host`, `user:pass@host`) are rejected; obvious non-public
targets are rejected — `localhost`, `*.localhost`, and loopback, private
(RFC 1918 / unique-local), link-local, unspecified, multicast, reserved, or
otherwise non-global IP literals (IPv4, IPv6, IPv4-mapped IPv6, and legacy
IPv4 shorthand such as `127.1`), classified with Python's `ipaddress`; and the
UTF-8 encoded body `{"url": ...}` (serialized with `json.dumps`, exactly as
aiohttp sends it) must be ≤ 16,384 bytes. DNS names are never resolved
client-side: public-looking hostnames go to AnySearch, which remains
authoritative. Ordinary query strings are allowed. These target rules apply to
Extract only; a custom `base_url` may still point at `localhost` for
development/testing.

**Response envelope.** `{"code": 0, "message": "success", "request_id":
"...", "data": {...}}` on success. Success requires HTTP < 400 and an integer
`code` of exactly 0 (`false`, `0.0`, and `"0"` are errors); anything else is
an error using `message`/`error_code` from the body. `data`, when present,
must be an object and is shape-checked per endpoint (malformed payloads raise
with `request_id`, never render as empty results; unknown keys are kept):

- search: `results` is required and is a list; `[]` is the only empty-result
  shape (a missing or null `results` is malformed). Each result is an object
  with a required string `title` (may be `""`) and a required string `url`;
  `snippet` and `content` are omitted when unavailable; when a key is present
  its value must be a string (`""` allowed, explicit `null` is malformed). `metadata`, when present, is an object; its documented
  `total_results` (integer) and `search_time_ms` (number) are type-checked.
- sub-domains: `domains` is a list (an unknown domain returns `[]`). Each
  entry is an object with a string `domain`, an optional string
  `description`, and a required `sub_domains` list (may be empty); each
  sub-domain is an object with a string `sub_domain`, an optional string
  `description`, and a `params` object keyed by name that is omitted when the
  sub-domain has no parameters (present → must be an object, `{}` allowed;
  explicit `null` is malformed). Every
  parameter definition must include a string `description`, a boolean
  `required`, and a numeric `sort_order`, so a missing `required` can never
  be shown as "optional".
- extract: `url` (the submitted URL), `title` (extracted title or `""`), and
  `content` (may be `""`) are all required strings.

**Remote error text.** Always passed through `redact_credentials()` (the
configured key, Bearer tokens, `as_sk_...` keys, email addresses, and
`password`/`api_key`/`token`/`secret`/`username`/`email` assignments) before
whitespace collapsing and truncation to 500 characters, so a credential near
the cut cannot survive partially. HTTP status, `error_code`, and `request_id`
are redacted, normalized to short safe tokens, and appended as diagnostics
(including on per-item batch errors).

**Generated credentials (HTTP 402).** Per AnySearch's docs, anonymous
Search/Extract quota exhaustion may return HTTP 402 whose message contains
generated `username`/`password`/`api_key` values, which must not enter
routine logs. When a 402 (or `402xx` business code, or an `auto_registered`
payload) carries credentials, the whole message is replaced by
`GENERATED_CREDENTIALS_MESSAGE`; status and `request_id` are kept, the
credentials are never shown, logged by this plugin, or persisted. An
ordinary 402 without credentials keeps its (redacted) message.

**Client identification header.** Every request sends `X-Anysearch-Client:
agent-zero-anysearch/<plugin version>` (constant `CLIENT_HEADER_VALUE`),
following the reference client's `_build_headers()` pattern with a distinct
value. Sent on anonymous and authenticated requests; carries no secret or
user data.

**`get_sub_domains` domain limit.** Capped at `MAX_DOMAINS` (5), matching the
reference client; rejected before any network call.

**`max_results` precedence.** `tools/anysearch.py`'s `_resolve_max_results()`
is the single source of truth for `search` and every `batch_search` item: an
explicit value wins; a missing key or explicit `null` falls back to the
plugin's configured default (itself 10 if unset). Request values and the
plugin-config default share `parse_int()`: integers, integral floats, and
decimal-integer strings are accepted and clamped to 1-10; booleans,
containers, fractions, NaN/inf, and other text are rejected.

**Per-action arguments.** `ACTION_ARGS` maps each action to the arguments it
accepts: `search` → `query`, `max_results`, `tag`, `sub_domain`, `domain`,
`params`, `sub_domain_params`, `zone`, `language`; `batch_search` → `queries`
(per-item search fields live inside each item; there are no shared batch
arguments); `get_sub_domains` → `domains`/`domain`; `extract` → `url`.
Anything else — a field valid for another action or an unknown key — returns
an `Error: unexpected argument(s) …` listing the names in sorted order,
before config, client, or network work, so no value is silently ignored. A
known field sent as `null` counts as absent; `method` (Agent Zero's
`extract_tools` alias for `action`) is accepted only when it equals the
action. The native schema's descriptions mark each field's action.

**`zone` / `action`.** `zone` must be `cn` or `intl` (case-insensitive,
blank = omitted); `language` stays a free-form string. The tool's `action`
must be a known string; omitted or `null` means `search`, while non-strings,
blank strings, and unknown names are rejected before any config, client, or
network work.

**Base URL.** `base_url` is an advanced trusted-endpoint override, not a
documented AnySearch deployment option. It must be `http(s)` with a host and
no query, fragment, or credentials. With an API key configured, `http://` is
rejected at client construction (before any request) unless the host is
`localhost` or a loopback IP literal (127.0.0.0/8, `::1`, IPv4-mapped),
decided without DNS; anonymous clients may use `http://`.

**Redirects.** Requests use `allow_redirects=False`; any 3xx is an
`AnySearchError`, so the Bearer credential and body are never replayed to
another origin or over a downgraded scheme regardless of aiohttp version.

**Successful payloads.** `_request()` passes `data` through
`redact_configured_key()`, which replaces the request's key (the one selected
from a comma-separated pool, if any) and its
`Bearer <key>` form in every string value and object key (structure and types
preserved) before validation and formatting, for every endpoint including
batch items. It deliberately does not redact other words or secrets in normal
web content.

**Untrusted output.** Search, batch, and sub-domain tool output starts with
`RESULTS_NOTICE`/`SUB_DOMAINS_NOTICE`; extract keeps `EXTRACT_NOTICE`. Remote
display text (titles, URLs, descriptions) goes through `_line()`: whitespace
runs collapse to one space and control, bidi-override and line/paragraph-
separator characters are escaped as `\uXXXX`. Identifiers (domain,
sub-domain, parameter names), metadata keys, and string metadata values go
through `_exact()`: unchanged when already single-line, otherwise rendered as
an escaped JSON string, so they stay exact and can never forge extra lines.
Every metadata key is kept, including null/empty values (e.g. `default=""`),
and nothing is truncated. Result bodies (`content`/`snippet`, extracted
content) stay multi-line under the notice.

**Timeout text.** `_format_seconds()` uses 6 significant digits
(`20`, `0.5`, `0.0001`, `1e-06`), so an accepted positive timeout never
renders as `0s`.

**Native tool schema.** The prompt embeds a JSON schema after the exact marker
`Input schema for tool_args:`; `helpers/responses_tools.py` uses it for the
Responses/native function tool (instead of its permissive fallback). Keep it in
sync with the tool arguments; it must not contain `{{` (prompt templating).
Action-specific requirements (`query`, `queries`, `domains`, `url`) are
enforced at runtime, not marked globally required.

## When AnySearch changes their API

1. Re-check the endpoint table above against the current first-party docs
   and reference client before changing request/response handling.
2. Update `helpers/anysearch_client.py` first, then `tools/anysearch.py`
   formatting if response fields changed, then the prompt contract if
   argument names or behavior changed.
3. Update or add tests in `tests/`; keep them mocked (no live network calls)
   except for a manual, explicitly-run smoke check.
4. Bump `version` in `plugin.yaml` and `CLIENT_HEADER_VALUE`.

## Non-goals

- This plugin does not replace, wrap, or modify `tools/search_engine.py`
  (SearXNG). The two tools are independent; enabling this plugin only adds
  `anysearch` alongside the existing `search_engine` tool.
- No new third-party Python dependency — the client reuses `aiohttp`,
  already used by `helpers/searxng.py`.

## Security

- The API key (when configured) is read via `models.get_api_key("anysearch")`
  (`API_KEY_ANYSEARCH` / `ANYSEARCH_API_KEY` / `ANYSEARCH_API_TOKEN` from
  `usr/.env`) and sent only as an `Authorization: Bearer` header to the
  configured `base_url`. It is not a tool argument, not stored in plugin
  config, and not intentionally included in exceptions or tool output;
  remote error text is redacted as described above. Other remote-supplied
  text (search results, extracted pages) is untrusted data.
- Service-generated credentials (HTTP 402 anonymous-quota flow,
  `auto_registered` payloads) are never surfaced or persisted; saving a key
  stays a deliberate, user-visible action via `usr/.env` (see project root
  `AGENTS.md`: never commit secrets).
