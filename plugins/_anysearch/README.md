# AnySearch

Optional web search integration for [AnySearch](https://www.anysearch.com) — a
unified real-time search API offering general web search, vertical-domain
search, parallel batch search, and full-page URL content extraction.

This plugin adds a **new, separate `anysearch` tool**. It does not replace,
modify, or disable the built-in `search_engine` (SearXNG) tool, which remains
Agent Zero's default web search behavior whether or not this plugin is
enabled.

## Why

SearXNG covers general keyword search well, but has no concept of
vertical-domain search (finance, code, travel, legal, etc.), batching
multiple queries in parallel, or extracting the full content of a specific
URL. AnySearch adds those capabilities as an opt-in extra, for
agents/tasks that benefit from them.

## Enabling

This plugin is disabled by default. Enable it from the Plugins panel in the
Web UI (or the plugin management API) to make the `anysearch` tool and its
prompt instructions available to agents.

## Authentication

AnySearch works without an API key, using anonymous access with lower rate
limits and quota. A blank or whitespace-only key is treated as no key. To use
an authenticated key with higher limits, set it the same way other Agent Zero
integrations do — add one of the following to
`usr/.env` (or the corresponding system environment variable):

```
API_KEY_ANYSEARCH=your-anysearch-api-key
```

(`ANYSEARCH_API_KEY` and `ANYSEARCH_API_TOKEN` are also recognized, matching
Agent Zero's standard `models.get_api_key()` lookup order.)

When a key is present it is sent as an `Authorization: Bearer <key>` header
on every request; without a key no `Authorization` header is sent. The key is
not a tool argument, is not stored in plugin settings, and is not
intentionally included in tool output or error messages. Remote error text is
redacted before it reaches the agent (the configured key, Bearer tokens,
`as_sk_...` keys, email addresses, and `password=`/`api_key=`/`token=`-style
assignments).

If the anonymous quota is exhausted, AnySearch may answer with HTTP 402 and a
message containing newly generated credentials. This plugin never shows or
stores those credentials: the agent only sees a notice that the anonymous
quota is exhausted and that an API key should be configured securely (with
the request ID for support).

### Custom base URL

`base_url` defaults to the production endpoint `https://api.anysearch.com`.
Changing it is an advanced override for a trusted endpoint only: an
authenticated request sends the Bearer credential to whatever endpoint is
configured. With an API key configured, a plain `http://` base URL is refused
before any request unless its host is a loopback development endpoint
(`localhost`, `127.0.0.0/8`, `::1`; decided without DNS lookups), so the
credential is never sent in plaintext to a remote host. Anonymous requests
(no key) may still use `http://`. The value must be an `http://` or
`https://` URL with a host and no query string, fragment, or embedded
credentials.

If an endpoint echoes the key used for the request back inside a successful
response, that key (and its `Bearer <key>` form) is replaced with `[REDACTED]`
before the data is shown to the agent. This covers only that AnySearch key
(with a comma-separated key pool, the key selected for the request), not
arbitrary secrets that might appear in web content. HTTP redirects are never
followed, so the credential cannot be forwarded to another origin.

## What the tool can do

Successful search, batch, sub-domain, and extract output is prefixed with a
short notice that the remote data is untrusted and not instructions. Remote
identifiers (domain, sub-domain and parameter names) and metadata are always
rendered on a single line with control characters escaped; values that would
otherwise change are shown as exact quoted strings.

- `search` — general or vertical-domain web search
- `batch_search` — 1-5 independent searches run in parallel; each item is
  isolated, so a malformed item or a failed backend call only produces an
  error for that item
- `get_sub_domains` — discover vertical domains/sub-domains; renders each
  parameter's required flag and description, uses `sort_order` for
  deterministic ordering, and preserves every additional metadata field in
  full without truncation, including empty/null values
- `extract` — full-page content extraction from a public `http(s)` URL
  without embedded credentials; the returned content may be HTML, plain text,
  JSON, or Markdown depending on the source (binary formats are unsupported).
  Obvious local/private targets (`localhost`, `*.localhost`, loopback,
  private, link-local, and other non-global IP literals) are rejected
  locally, and the request body is limited to 16 KiB. Host names are not
  resolved client-side; AnySearch remains authoritative for whether a URL is
  reachable and public.

See [`prompts/agent.system.tool.anysearch.md`](prompts/agent.system.tool.anysearch.md)
for the exact tool contract given to the agent.

## Configuration

Non-secret settings live in [`default_config.yaml`](default_config.yaml):
`base_url`, `timeout` (seconds), and `max_results` (1-10, the default used
when the agent doesn't specify one). `batch_search`'s limit of 5 queries per
call is a fixed AnySearch protocol constraint, not a setting.

## Maintenance

See [`MAINTENANCE.md`](MAINTENANCE.md).
