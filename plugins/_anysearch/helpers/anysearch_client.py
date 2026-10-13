"""Minimal async HTTP client for the AnySearch REST API.

Covers the documented REST surface (https://www.anysearch.com/docs and the
first-party reference client anysearch-ai/anysearch-skill,
scripts/anysearch_cli.py):
- POST /v1/search        general + vertical-domain search
- GET  /v1/sub-domains    vertical-domain / sub-domain capability discovery
- POST /v1/extract        full-page URL content extraction

There is no dedicated server-side batch endpoint; "batch search" is
implemented client-side as bounded, concurrent calls to /v1/search, matching
the documented batch_search contract (1-5 queries, parallel execution, a
single item's failure — validation or backend — does not block the others).

Vertical-domain routing: AnySearch's REST search request takes a single
`tag` field: a fully-qualified routing key, e.g. "finance.quote". GET
/v1/sub-domains already returns `sub_domain` values fully qualified in that
same form — never prefix a returned `sub_domain` value with `domain`; it is
already complete. So `sub_domain` here is a `tag` alias, never concatenated
with `domain` (that would produce the invalid "finance.finance.quote").
`domain` alone is only a local validation hint; it is never sent over the
wire as a separate field.

Authentication: an API key is sent as `Authorization: Bearer <key>` when
provided; omitting it uses AnySearch's anonymous access (lower rate limits
and quota), and no Authorization header is sent at all. The key is never
intentionally placed into exception messages. Remote/network error text is
redacted before it is placed into an AnySearchError: the configured key (bare
and `Bearer <key>`), any Bearer token, `as_sk_...` keys, and sensitive
assignments such as `password=...`/`api_key=...`/`username=...`. A remote
message that carries service-generated credentials (the anonymous-quota
HTTP 402 flow, or an `auto_registered` payload) is replaced entirely by
GENERATED_CREDENTIALS_MESSAGE; those credentials are never persisted.

Successful responses must carry an integer business `code` of 0 and are
shape-checked per endpoint, so malformed payloads raise instead of being
rendered as empty results.

Client identification: every request also sends an `X-Anysearch-Client`
header (a fixed, non-secret string identifying this integration), matching
the pattern of AnySearch's official reference clients (anysearch_cli.py:
_build_headers()).

get_sub_domains is capped at MAX_DOMAINS (5) per call, matching the official
reference client's own limit (anysearch_cli.py: cmd_get_sub_domains()).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import re
import socket
from typing import Any, Iterable
from urllib.parse import urlsplit

import aiohttp

DEFAULT_BASE_URL = "https://api.anysearch.com"
DEFAULT_TIMEOUT = 20.0
MAX_BATCH_SIZE = 5
MAX_RESULTS_RANGE = (1, 10)
MAX_DOMAINS = 5
# Official /v1/extract request-body limit (UTF-8 encoded JSON).
MAX_EXTRACT_BODY_BYTES = 16 * 1024
# Remote error text is untrusted; keep what reaches the model bounded.
MAX_REMOTE_MESSAGE_CHARS = 500

# AnySearch's official reference clients send an X-Anysearch-Client header
# identifying the calling integration, on both anonymous and authenticated
# requests. The reference CLI's own value ("skill/<version>") identifies the
# AnySearch Skill client, not this integration, so this uses a distinct,
# stable identifier for the Agent Zero plugin instead. It never carries a
# secret or any user data.
CLIENT_HEADER_VALUE = "agent-zero-anysearch/1.1.0"

# Official /v1/search `zone` values.
ALLOWED_ZONES = ("cn", "intl")

# Shown instead of any remote message that carries service-generated
# credentials (e.g. the anonymous-quota HTTP 402 flow). Those credentials are
# never exposed through tool output and never persisted by this integration.
GENERATED_CREDENTIALS_MESSAGE = (
    "AnySearch anonymous quota is exhausted. The service returned generated "
    "credentials, but this integration does not expose or persist credentials "
    "through tool output. Configure an API key securely and retry."
)

_ALLOWED_URL_SCHEMES = ("http", "https")
_SENSITIVE_NAME = (
    r"(?:password|passwd|pwd|api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|"
    r"auth[_-]?token|token|secret|client[_-]?secret|user[_-]?name|username|email)"
)
# `name=value`, `name: value`, `"name": "value"` (quoted or bare values)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)(" + _SENSITIVE_NAME + r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&\"'<>)\]}]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]+")
_ANYSEARCH_KEY_RE = re.compile(r"\bas_sk_[A-Za-z0-9_\-]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_GENERATED_CREDENTIAL_KEYS = ("auto_registered", "api_key", "apikey", "password", "token")
_DIAGNOSTIC_TOKEN_RE = re.compile(r"[^A-Za-z0-9._:\-]")
_MAX_DIAGNOSTIC_TOKEN_CHARS = 128


class AnySearchError(Exception):
    """Raised for HTTP failures, timeouts, malformed responses, and
    caller-side validation errors (e.g. conflicting vertical-search routing).

    The client never intentionally puts the API key into the message and
    redacts credentials from remote/network error text (see
    redact_credentials). The message may still contain other remote-supplied
    text (bounded in length), which should be treated as untrusted data.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = _normalize_diagnostic_token(error_code)
        self.status = status if isinstance(status, int) and not isinstance(status, bool) else None
        self.request_id = _normalize_diagnostic_token(request_id)

    def diagnostics(self) -> str:
        """Compact, sanitized `[HTTP 429, error_code=..., request_id=...]`
        suffix built only from normalized fields; empty when none exist."""
        parts = []
        if self.status is not None:
            parts.append(f"HTTP {self.status}")
        if self.error_code:
            parts.append(f"error_code={self.error_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return f" [{', '.join(parts)}]" if parts else ""


def _normalize_diagnostic_token(value: Any) -> str | None:
    """Reduce a remote identifier (request_id / error_code) to a short,
    single-line token of safe characters, or None when nothing is left."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (str, int)):
        return None
    token = _DIAGNOSTIC_TOKEN_RE.sub("", str(value).strip())
    token = token[:_MAX_DIAGNOSTIC_TOKEN_CHARS]
    return token or None


def redact_credentials(text: str, api_key: str | None = None) -> str:
    """Redact the configured key (bare and Bearer forms), any `Bearer <token>`,
    AnySearch-style `as_sk_...` keys, email addresses, and obvious sensitive
    assignments such as `password=...`, `api_key: ...`, `"token": "..."`,
    `username=...`."""
    if api_key:
        text = text.replace(f"Bearer {api_key}", "Bearer [REDACTED]")
        text = text.replace(api_key, "[REDACTED]")
    text = _CREDENTIAL_ASSIGNMENT_RE.sub(lambda m: m.group(1) + "[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _ANYSEARCH_KEY_RE.sub("[REDACTED]", text)
    return _EMAIL_RE.sub("[REDACTED_EMAIL]", text)


def redact_configured_key(value: Any, api_key: str | None) -> Any:
    """Recursively replace the configured key (and its `Bearer <key>` form)
    in every string — values and object keys — of a successful payload,
    preserving structure and types. Only the configured AnySearch key is
    redacted; ordinary web content is otherwise left unchanged."""
    if not api_key:
        return value
    if isinstance(value, str):
        return value.replace(f"Bearer {api_key}", "Bearer [REDACTED]").replace(api_key, "[REDACTED]")
    if isinstance(value, list):
        return [redact_configured_key(item, api_key) for item in value]
    if isinstance(value, dict):
        return {
            redact_configured_key(key, api_key) if isinstance(key, str) else key: redact_configured_key(item, api_key)
            for key, item in value.items()
        }
    return value


def _contains_generated_credentials(message: Any, data: Any) -> bool:
    text = message if isinstance(message, str) else ""
    if _ANYSEARCH_KEY_RE.search(text) or re.search(
        r"(?i)(?:password|passwd|api[_-]?key|apikey|token|secret)[\"']?\s*[:=]", text
    ):
        return True
    if isinstance(data, dict):
        return any(key in data for key in _GENERATED_CREDENTIAL_KEYS)
    return False


def _is_quota_status(status: int, code: Any) -> bool:
    return status == 402 or (
        type(code) is int and code != 0 and str(abs(code)).startswith("402")
    )


def normalize_api_key(api_key: Any) -> str | None:
    """Return a usable key, or None for missing/blank/whitespace-only values
    and Agent Zero's "None" placeholder, so an empty `Bearer ` header can
    never be sent. Non-string keys are a configuration error."""
    if api_key is None:
        return None
    if not isinstance(api_key, str):
        raise AnySearchError(f"api_key must be a string, got {type(api_key).__name__}")
    key = api_key.strip()
    if not key or key == "None":
        return None
    return key


def parse_int(value: Any, field: str) -> int:
    """Strict integer parsing shared by request and config values: accepts an
    int, an integral finite float, or a decimal-integer string; rejects bool,
    None, containers, fractions, NaN/inf, and other text."""
    if isinstance(value, bool):
        numeric = None
    elif isinstance(value, int):
        numeric = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        numeric = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        numeric = int(value)
    else:
        numeric = None
    if numeric is None:
        lo, hi = MAX_RESULTS_RANGE
        raise AnySearchError(f"{field} must be an integer from {lo} to {hi}, got {value!r}")
    return numeric


def _normalize_timeout(value: Any) -> float:
    """Coerce a caller/config-supplied timeout into a strictly positive,
    finite float, or raise AnySearchError.

    A value that is non-numeric, zero, negative, NaN, or +/-inf would either
    fail confusingly deep inside aiohttp or (for 0) silently disable the
    timeout altogether, so all of these are rejected up front.
    """
    if isinstance(value, bool):
        raise AnySearchError(f"timeout must be a number, got {value!r}")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise AnySearchError(f"timeout must be a number, got {value!r}") from None
    if not math.isfinite(numeric):
        raise AnySearchError(f"timeout must be finite, got {value!r}")
    if numeric <= 0:
        raise AnySearchError(f"timeout must be greater than 0, got {value!r}")
    return numeric


def _format_seconds(seconds: float) -> str:
    """Stable, truthful seconds with 6 significant digits: 20 -> '20',
    0.5 -> '0.5', 0.0001 -> '0.0001', 0.000001 -> '1e-06'. Never renders an
    accepted positive timeout as '0'."""
    return format(seconds, ".6g")


def _validate_http_url(value: Any, field: str) -> str:
    """Return a stripped http(s) URL with a host, or raise AnySearchError."""
    if not isinstance(value, str):
        raise AnySearchError(f"{field} must be a string, got {type(value).__name__}")
    url = value.strip()
    if not url:
        raise AnySearchError(f"{field} must not be empty")
    # Error messages below never echo the URL (or any part of it before the
    # userinfo check), so credentials embedded in a malformed URL cannot leak
    # into the error text.
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url):
        raise AnySearchError(f"{field} must not contain whitespace or control characters")
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        parts.port  # raises ValueError for a malformed port
    except ValueError:
        raise AnySearchError(f"{field} is not a valid URL") from None
    if parts.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        raise AnySearchError(f"{field} must use http:// or https://")
    if not hostname:
        raise AnySearchError(f"{field} must include a host")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        # never forward URL credentials (user@host, user:pass@host) anywhere
        raise AnySearchError(f"{field} must not embed credentials (user@host)")
    return url


def _non_public_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    # most specific first: ipaddress also marks link-local/unspecified as private
    if ip.is_loopback:
        return "a loopback address"
    if ip.is_unspecified:
        return "an unspecified address"
    if ip.is_link_local:
        return "a link-local address"
    if ip.is_multicast:
        return "a multicast address"
    if ip.is_reserved:
        return "a reserved or non-global address"
    if ip.is_private:
        return "a private address"
    if not ip.is_global:
        return "a reserved or non-global address"
    return None


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an IP literal without any DNS lookup. Also accepts the legacy
    IPv4 shorthand forms (e.g. `127.1`, `2130706433`, `0x7f.1`) that many
    HTTP stacks still interpret as addresses."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-fA-Fx.]+", host) and re.search(r"\d", host):
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return None
    return None


def _is_loopback_host(host: str) -> bool:
    """`localhost` or a loopback IP literal (127.0.0.0/8, ::1, IPv4-mapped);
    decided without DNS."""
    host = host.rstrip(".").lower()
    if host == "localhost":
        return True
    ip = _ip_literal(host.split("%", 1)[0])
    if ip is None:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return (mapped or ip).is_loopback


def validate_extract_target(value: Any) -> str:
    """Extract-only rules on top of _validate_http_url: the official contract
    takes a public absolute http(s) URL. Obvious non-public targets —
    `localhost`/`*.localhost` and loopback, private, link-local, unspecified,
    multicast, reserved, or otherwise non-global IP literals — are rejected
    locally. Hostnames are never resolved here; AnySearch remains
    authoritative for DNS names. The encoded JSON body must fit the
    documented 16 KiB limit."""
    url = _validate_http_url(value, "url")
    host = (urlsplit(url).hostname or "").rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise AnySearchError(f"url must be a public URL; {host!r} is a local host name")
    ip = _ip_literal(host.split("%", 1)[0])
    if ip is not None:
        reason = _non_public_reason(ip)
        if reason:
            raise AnySearchError(f"url must be a public URL; {host!r} is {reason}")
    body_size = len(extract_body_bytes(url))
    if body_size > MAX_EXTRACT_BODY_BYTES:
        raise AnySearchError(
            f"url is too long: the extract request body would be {body_size} bytes "
            f"(limit {MAX_EXTRACT_BODY_BYTES})"
        )
    return url


def extract_body_bytes(url: str) -> bytes:
    """The exact bytes sent for an extract request: aiohttp serializes `json=`
    with json.dumps (its default serializer) and encodes as UTF-8."""
    return json.dumps({"url": url}).encode("utf-8")


def _validate_base_url(value: Any) -> str:
    """`None`/blank falls back to DEFAULT_BASE_URL; anything else must be a
    plain http(s) origin (optionally with a path prefix) — no query string,
    fragment, or embedded credentials, since request paths are appended."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_BASE_URL
    url = _validate_http_url(value, "base_url")
    parts = urlsplit(url)
    if parts.query or parts.fragment:
        raise AnySearchError("base_url must not contain a query string or fragment")
    return url.rstrip("/")


def _clamp_max_results(value: Any) -> int:
    """Accept an int, an integral float, or a decimal-integer string, and
    clamp it to MAX_RESULTS_RANGE. Anything else (bool, None, containers,
    fractional numbers, non-numeric text) is a caller mistake and raises."""
    return clamp_max_results(value, "max_results")


def clamp_max_results(value: Any, field: str) -> int:
    lo, hi = MAX_RESULTS_RANGE
    return max(lo, min(hi, parse_int(value, field)))


def _optional_routing_str(value: Any, field: str) -> str | None:
    """Vertical routing fields: absent/None, or a non-empty string. Any other
    type — and a blank string — is rejected so a malformed routing argument
    can never silently turn a vertical search into a general one."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise AnySearchError(f"{field} must be a string, got {type(value).__name__}")
    cleaned = value.strip()
    if not cleaned:
        raise AnySearchError(f"{field} must not be blank; omit it for a general search")
    return cleaned


def _optional_hint_str(value: Any, field: str) -> str | None:
    """zone/language hints: absent/None or blank means "not set"; any other
    non-string type is rejected."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise AnySearchError(f"{field} must be a string, got {type(value).__name__}")
    return value.strip() or None


def _optional_zone(value: Any) -> str | None:
    zone = _optional_hint_str(value, "zone")
    if zone is None:
        return None
    zone = zone.lower()
    if zone not in ALLOWED_ZONES:
        raise AnySearchError(f"zone must be one of {', '.join(ALLOWED_ZONES)}, got {value!r}")
    return zone


def resolve_tag(*, tag: Any = None, domain: Any = None, sub_domain: Any = None) -> str | None:
    """Resolve the single REST `tag` value AnySearch's /v1/search expects.

    `tag` is the REST-native argument. `sub_domain` is accepted as an alias
    for `tag` (it already arrives fully qualified, e.g. "finance.quote", from
    GET /v1/sub-domains). `domain` is only a validation/compatibility hint
    and is never concatenated onto `sub_domain`/`tag`.

    Raises AnySearchError (before any network call) when:
    - any of the three is present but not a non-empty string, or
    - `tag` and `sub_domain` are both given and disagree, or
    - `domain` is given without a `tag`/`sub_domain`, or
    - `domain` disagrees with the domain prefix of the resolved tag.
    """
    tag = _optional_routing_str(tag, "tag")
    sub_domain = _optional_routing_str(sub_domain, "sub_domain")
    domain = _optional_routing_str(domain, "domain")

    if tag and sub_domain and tag != sub_domain:
        raise AnySearchError(
            f"conflicting vertical search routing: tag={tag!r} does not match sub_domain={sub_domain!r}"
        )

    effective_tag = tag or sub_domain

    if domain and not effective_tag:
        raise AnySearchError(
            f"domain={domain!r} was given without a tag or sub_domain; AnySearch routes "
            "by the fully-qualified tag returned by get_sub_domains (e.g. 'finance.quote'), "
            "not by domain alone"
        )

    if domain and effective_tag:
        tag_domain_part = effective_tag.split(".", 1)[0]
        if tag_domain_part != domain:
            raise AnySearchError(
                f"domain={domain!r} does not match the domain prefix of tag={effective_tag!r}"
            )

    return effective_tag


def resolve_params(params: Any = None, sub_domain_params: Any = None) -> dict[str, Any] | None:
    """Resolve `params` and its `sub_domain_params` alias into one object.

    `None` means the alias is absent; any dict (including `{}`) means it is
    present. Each present alias must be a dict. When both are present they
    must be exactly equal (`{}` + `{}` is fine, `{}` + non-empty is a
    conflict); one alias is never silently chosen over the other. An empty
    result means "no params" and returns None.
    """
    present: list[dict[str, Any]] = []
    for field, value in (("params", params), ("sub_domain_params", sub_domain_params)):
        if value is None:
            continue
        if not isinstance(value, dict):
            raise AnySearchError(
                f"{field} must be an object of parameter names to values, got {type(value).__name__}"
            )
        present.append(value)
    if len(present) == 2 and present[0] != present[1]:
        raise AnySearchError(
            "conflicting sub-domain parameters: params and sub_domain_params differ; send only one"
        )
    return dict(present[0]) if present and present[0] else None


def _malformed(what: str, request_id: Any) -> AnySearchError:
    return AnySearchError(f"AnySearch returned a malformed response: {what}", request_id=request_id)


def _check_optional_str(obj: dict[str, Any], key: str, where: str, request_id: Any) -> None:
    value = obj.get(key)
    if value is not None and not isinstance(value, str):
        raise _malformed(f"{where}.{key} must be a string, got {type(value).__name__}", request_id)


def _check_present_str(obj: dict[str, Any], key: str, where: str, request_id: Any) -> None:
    if key in obj and not isinstance(obj[key], str):
        raise _malformed(
            f"{where}.{key} must be a string when present (omit it when unavailable), got {type(obj[key]).__name__}",
            request_id,
        )


def _check_required_str(obj: dict[str, Any], key: str, where: str, request_id: Any) -> None:
    if not isinstance(obj.get(key), str):
        raise _malformed(f"{where}.{key} must be a string", request_id)


def _check_number(obj: dict[str, Any], key: str, where: str, request_id: Any, *, integer: bool, required: bool) -> None:
    if key not in obj or obj[key] is None:
        if required:
            raise _malformed(f"{where}.{key} is required", request_id)
        return
    value = obj[key]
    kinds = (int,) if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, kinds):
        kind = "an integer" if integer else "a number"
        raise _malformed(f"{where}.{key} must be {kind}, got {type(value).__name__}", request_id)


def _validate_search_data(data: dict[str, Any], request_id: Any) -> dict[str, Any]:
    """Official /v1/search contract: `data.results` is required and is a list
    (an empty list is the only empty-result shape). Each result is an object
    with a required string `title` (may be "") and required string `url`;
    `snippet` and `content` are omitted when unavailable and must be strings
    when present (an explicit null is malformed). `metadata`, when present, is an object whose documented
    `total_results` (integer) and `search_time_ms` (number) are type-checked.
    Unknown keys are kept."""
    if "results" not in data:
        raise _malformed("data.results is required", request_id)
    results = data["results"]
    if not isinstance(results, list):
        raise _malformed(f"data.results must be a list, got {type(results).__name__}", request_id)
    for i, item in enumerate(results):
        where = f"data.results[{i}]"
        if not isinstance(item, dict):
            raise _malformed(f"{where} must be an object", request_id)
        _check_required_str(item, "title", where, request_id)
        _check_required_str(item, "url", where, request_id)
        # omitted when unavailable; when present (even null) must be a string
        _check_present_str(item, "snippet", where, request_id)
        _check_present_str(item, "content", where, request_id)
    metadata = data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise _malformed(f"data.metadata must be an object, got {type(metadata).__name__}", request_id)
        _check_number(metadata, "total_results", "data.metadata", request_id, integer=True, required=False)
        _check_number(metadata, "search_time_ms", "data.metadata", request_id, integer=False, required=False)
    return data


def _validate_sub_domains_data(data: dict[str, Any], request_id: Any) -> dict[str, Any]:
    """Official /v1/sub-domains contract: `data.domains` is a list (an unknown
    domain yields `[]`). Every domain entry is an object with a string
    `domain` and a `sub_domains` list (may be empty); every sub-domain is an
    object with a string `sub_domain` and, when it has parameters, a `params`
    object (omitted otherwise; explicit null is malformed); every parameter
    definition is an
    object that includes a string `description`, a boolean `required`, and a
    numeric `sort_order`. Descriptions are type-checked when present on
    domains/sub-domains. Unknown keys are kept."""
    domains = data.get("domains")
    if not isinstance(domains, list):
        raise _malformed(f"data.domains must be a list, got {type(domains).__name__}", request_id)
    for i, entry in enumerate(domains):
        where = f"data.domains[{i}]"
        if not isinstance(entry, dict):
            raise _malformed(f"{where} must be an object", request_id)
        _check_required_str(entry, "domain", where, request_id)
        _check_optional_str(entry, "description", where, request_id)
        sub_domains = entry.get("sub_domains")
        if not isinstance(sub_domains, list):
            raise _malformed(f"{where}.sub_domains must be a list", request_id)
        for j, sub in enumerate(sub_domains):
            sub_where = f"{where}.sub_domains[{j}]"
            if not isinstance(sub, dict):
                raise _malformed(f"{sub_where} must be an object", request_id)
            _check_required_str(sub, "sub_domain", sub_where, request_id)
            _check_optional_str(sub, "description", sub_where, request_id)
            # omitted when a sub-domain has no parameters; when present
            # (even null) it must be an object ({} is accepted)
            if "params" not in sub:
                continue
            params = sub["params"]
            if not isinstance(params, dict):
                raise _malformed(f"{sub_where}.params must be an object keyed by parameter name", request_id)
            for name, meta in params.items():
                param_where = f"{sub_where}.params[{name!r}]"
                if not isinstance(meta, dict):
                    raise _malformed(f"{param_where} must be an object", request_id)
                _check_required_str(meta, "description", param_where, request_id)
                if not isinstance(meta.get("required"), bool):
                    raise _malformed(f"{param_where}.required must be a boolean", request_id)
                _check_number(meta, "sort_order", param_where, request_id, integer=False, required=True)
    return data


def _validate_extract_data(data: dict[str, Any], request_id: Any) -> dict[str, Any]:
    """Official /v1/extract contract: `url` (the submitted URL), `title`
    (extracted title or ""), and `content` (cleaned HTML, plain text, JSON,
    or Markdown; may be empty) are all required strings. Non-string content
    is never stringified."""
    for key in ("url", "title", "content"):
        _check_required_str(data, key, "data", request_id)
    return data


class AnySearchClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = DEFAULT_BASE_URL,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> None:
        # blank/whitespace-only keys and Agent Zero's "None" sentinel mean no
        # key: anonymous access sends no Authorization header at all
        self.api_key = normalize_api_key(api_key)
        # custom base_url is an advanced, trusted endpoint override: an
        # authenticated request sends the Bearer credential to it
        self.base_url = _validate_base_url(base_url)
        # never send a Bearer credential over plaintext to a remote host;
        # plain http is allowed only for loopback development endpoints
        base_parts = urlsplit(self.base_url)
        if (
            self.api_key
            and base_parts.scheme.lower() == "http"
            and not _is_loopback_host(base_parts.hostname or "")
        ):
            raise AnySearchError(
                "base_url uses plain http:// for a non-loopback host while an API key is "
                "configured; use https:// so the Bearer credential is not sent in plaintext"
            )
        # `None` (an omitted config value) falls back to the default; any
        # other explicit value is validated and rejected if malformed
        self.timeout = DEFAULT_TIMEOUT if timeout is None else _normalize_timeout(timeout)

    @property
    def is_anonymous(self) -> bool:
        return not bool(self.api_key)

    def _sanitize(self, text: Any) -> str | None:
        """Redact credentials (see redact_credentials) from remote/network-
        supplied text, collapse whitespace/control characters, and bound its
        length, before it is ever placed into an AnySearchError.

        Redaction runs on the full text before truncation, so a credential
        near the cut can never survive partially.
        """
        if text is None:
            return None
        text = redact_credentials(str(text), self.api_key)
        text = " ".join(text.split())
        if len(text) > MAX_REMOTE_MESSAGE_CHARS:
            text = text[:MAX_REMOTE_MESSAGE_CHARS].rstrip() + "…"
        return text

    def _clean_identifier(self, value: Any) -> Any:
        return self._sanitize(value) if isinstance(value, str) else value

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Anysearch-Client": CLIENT_HEADER_VALUE,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: Iterable[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        client_timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.request(
                    method,
                    url,
                    json=json_body,
                    params=list(params) if params is not None else None,
                    headers=self._headers(),
                    # the REST endpoints do not redirect; never follow one, so
                    # the Bearer credential and request body cannot be replayed
                    # to another origin or downgraded, whatever the aiohttp version
                    allow_redirects=False,
                ) as response:
                    status = response.status
                    if 300 <= status < 400:
                        raise AnySearchError(
                            f"AnySearch returned a redirect (HTTP {status}); redirects are not followed",
                            status=status,
                        )
                    try:
                        payload = await response.json(content_type=None)
                    except Exception as exc:  # malformed / non-JSON body
                        raise AnySearchError(
                            f"AnySearch returned a non-JSON response (HTTP {status})",
                            status=status,
                        ) from exc
        except asyncio.TimeoutError as exc:
            raise AnySearchError(
                f"AnySearch request timed out after {_format_seconds(self.timeout)}s"
            ) from exc
        except aiohttp.ClientError as exc:
            # transport-layer text is sanitized on the same footing as
            # remote error messages rather than assumed safe
            raise AnySearchError(self._sanitize(f"AnySearch request failed: {exc}")) from exc

        if not isinstance(payload, dict):
            raise AnySearchError(
                f"AnySearch returned an unexpected response shape (HTTP {status})",
                status=status,
            )

        # identifiers are redacted before normalization so a key-shaped value
        # can never survive into diagnostics
        request_id = self._clean_identifier(payload.get("request_id"))
        error_code = self._clean_identifier(payload.get("error_code"))
        code = payload.get("code")
        # success requires a genuine integer business code 0 (not False, 0.0, "0")
        success_code = type(code) is int and code == 0
        if status >= 400 or not success_code:
            raw_message = payload.get("message")
            if _contains_generated_credentials(raw_message, payload.get("data")) and (
                _is_quota_status(status, code) or (
                    isinstance(payload.get("data"), dict) and "auto_registered" in payload["data"]
                )
            ):
                # the remote message itself carries generated credentials: it
                # is replaced entirely, never redacted piecemeal or surfaced
                message = GENERATED_CREDENTIALS_MESSAGE
            elif code is None and status < 400:
                message = "AnySearch response is missing the expected 'code' envelope field"
                if isinstance(raw_message, str) and raw_message.strip():
                    message += f": {raw_message}"
            elif status < 400:
                message = f"AnySearch returned a non-success or non-integer business code {code!r}"
                if isinstance(raw_message, str) and raw_message.strip():
                    message += f": {raw_message}"
            else:
                message = raw_message if isinstance(raw_message, str) and raw_message.strip() else "unknown AnySearch error"
            raise AnySearchError(
                self._sanitize(message) or "unknown AnySearch error",
                error_code=error_code,
                status=status,
                request_id=request_id,
            )

        data = payload.get("data")
        if data is not None and not isinstance(data, dict):
            raise AnySearchError(
                f"AnySearch returned an unexpected 'data' shape (HTTP {status})",
                status=status,
                request_id=request_id,
            )

        # a (custom or misbehaving) endpoint must never be able to echo the
        # configured key back into tool output through a successful payload
        if self.api_key and data is not None:
            payload = dict(payload, data=redact_configured_key(data, self.api_key))
        return payload

    async def search(
        self,
        query: Any,
        *,
        max_results: Any = None,
        tag: Any = None,
        domain: Any = None,
        sub_domain: Any = None,
        params: Any = None,
        sub_domain_params: Any = None,
        zone: Any = None,
        language: Any = None,
    ) -> dict[str, Any]:
        """Validate every argument locally, then POST /v1/search.

        Any validation failure raises AnySearchError before a network call.
        """
        if not isinstance(query, str):
            raise AnySearchError(f"query must be a string, got {type(query).__name__}")
        if not query.strip():
            raise AnySearchError("query must not be empty")

        resolved_tag = resolve_tag(tag=tag, domain=domain, sub_domain=sub_domain)
        resolved_params = resolve_params(params, sub_domain_params)
        resolved_zone = _optional_zone(zone)
        resolved_language = _optional_hint_str(language, "language")

        body: dict[str, Any] = {
            "query": query,
            # None (omitted) uses the API's documented default of 10
            "max_results": _clamp_max_results(MAX_RESULTS_RANGE[1] if max_results is None else max_results),
        }
        if resolved_tag:
            body["tag"] = resolved_tag
        if resolved_params:
            body["params"] = resolved_params
        if resolved_zone:
            body["zone"] = resolved_zone
        if resolved_language:
            body["language"] = resolved_language

        payload = await self._request("POST", "/v1/search", json_body=body)
        return _validate_search_data(payload.get("data") or {}, payload.get("request_id"))

    async def get_sub_domains(self, domains: Any) -> dict[str, Any]:
        if isinstance(domains, str):
            domain_list = [domains]
        elif domains is None:
            domain_list = []
        elif isinstance(domains, (list, tuple)):
            domain_list = list(domains)
        else:
            # a dict would otherwise be silently iterated as its keys
            raise AnySearchError(
                f"domains must be a string or a list of strings, got {type(domains).__name__}"
            )
        if not all(isinstance(d, str) for d in domain_list):
            raise AnySearchError("domains must all be strings")
        domain_list = [d for d in (d.strip() for d in domain_list) if d]
        if not domain_list:
            raise AnySearchError("at least one domain is required")
        if len(domain_list) > MAX_DOMAINS:
            raise AnySearchError(
                f"get_sub_domains supports at most {MAX_DOMAINS} domains, got {len(domain_list)}"
            )

        payload = await self._request(
            "GET", "/v1/sub-domains", params=[("domain", d) for d in domain_list]
        )
        return _validate_sub_domains_data(payload.get("data") or {}, payload.get("request_id"))

    async def extract(self, url: Any) -> dict[str, Any]:
        """Validate `url` locally (public http/https URL with a host, no
        embedded credentials, body within 16 KiB — see
        validate_extract_target), then POST /v1/extract. Invalid URLs raise
        before any network call."""
        target = validate_extract_target(url)
        payload = await self._request("POST", "/v1/extract", json_body={"url": target})
        return _validate_extract_data(payload.get("data") or {}, payload.get("request_id"))

    async def batch_search(
        self, queries: Any, *, max_batch_size: int = MAX_BATCH_SIZE
    ) -> list[dict[str, Any]]:
        """Run 1..`max_batch_size` independent searches concurrently.

        Only batch-level problems fail the whole call: `queries` not a list,
        an empty list, or more than `max_batch_size` items. After that, every
        item is isolated: a malformed item (non-object, missing/blank/non-
        string query, bad max_results, conflicting routing, bad params, ...)
        produces its own error entry without any network request, and a
        backend failure on one item never affects its siblings.

        Returns one entry per input item, in input order:
        {"index", "query", "ok": True, "data"} or
        {"index", "query", "ok": False, "error", "request_id"?}.
        """
        if not isinstance(queries, list):
            raise AnySearchError(f"queries must be a list, got {type(queries).__name__}")
        if not queries:
            raise AnySearchError("queries must not be empty")
        if len(queries) > max_batch_size:
            raise AnySearchError(
                f"batch_search supports at most {max_batch_size} queries per call, got {len(queries)}"
            )

        async def run_one(index: int, spec: Any) -> dict[str, Any]:
            query = spec.get("query") if isinstance(spec, dict) else None
            entry: dict[str, Any] = {
                "index": index,
                "query": query if isinstance(query, str) else "",
            }
            try:
                if not isinstance(spec, dict):
                    raise AnySearchError(
                        f"item must be an object with a 'query' field, got {type(spec).__name__}"
                    )
                data = await self.search(
                    query,
                    max_results=spec.get("max_results"),
                    tag=spec.get("tag"),
                    domain=spec.get("domain"),
                    sub_domain=spec.get("sub_domain"),
                    params=spec.get("params"),
                    sub_domain_params=spec.get("sub_domain_params"),
                    zone=spec.get("zone"),
                    language=spec.get("language"),
                )
                entry.update(ok=True, data=data)
            except AnySearchError as exc:
                entry.update(ok=False, error=str(exc) + exc.diagnostics())
                if exc.request_id:
                    entry["request_id"] = exc.request_id
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # an unexpected failure in one item must not abort siblings
                entry.update(
                    ok=False,
                    error=self._sanitize(f"unexpected error: {type(exc).__name__}: {exc}"),
                )
            return entry

        # gather() preserves input order regardless of completion order
        return list(await asyncio.gather(*(run_one(i, spec) for i, spec in enumerate(queries))))
