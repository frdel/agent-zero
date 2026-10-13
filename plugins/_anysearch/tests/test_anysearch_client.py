from __future__ import annotations

import asyncio
import math

import aiohttp
import pytest

from plugins._anysearch.helpers.anysearch_client import (
    AnySearchClient,
    AnySearchError,
    CLIENT_HEADER_VALUE,
    MAX_DOMAINS,
    resolve_tag,
)


class _FakeResponse:
    def __init__(self, status=200, json_data=None, raise_json=False):
        self.status = status
        self._json_data = json_data
        self._raise_json = raise_json

    async def json(self, content_type=None):
        if self._raise_json:
            raise ValueError("not json")
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeRequestCtx:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def __await__(self):  # not used; request() is used as a context manager directly
        raise AssertionError("request() must be used with 'async with', not awaited")

    async def __aenter__(self):
        if self._exc:
            raise self._exc
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Records the single request made and returns a scripted response."""

    last_call: dict | None = None

    def __init__(self, response=None, exc=None, timeout=None):
        self.response = response
        self.exc = exc
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def request(self, method, url, *, json=None, params=None, headers=None, allow_redirects=True):
        _FakeSession.last_call = {
            "method": method,
            "url": url,
            "json": json,
            "params": params,
            "headers": headers,
            "allow_redirects": allow_redirects,
        }
        return _FakeRequestCtx(response=self.response, exc=self.exc)


def _patch_session(monkeypatch, *, response=None, exc=None):
    def factory(*, timeout=None):
        return _FakeSession(response=response, exc=exc, timeout=timeout)

    monkeypatch.setattr(
        "plugins._anysearch.helpers.anysearch_client.aiohttp.ClientSession", factory
    )


SUCCESS_ENVELOPE = {
    "code": 0,
    "message": "success",
    "request_id": "11111111-1111-1111-1111-111111111111",
    "data": {
        "results": [
            {
                "title": "Go 1.26 Release Notes",
                "url": "https://go.dev/doc/go1.26",
                "snippet": "Introduction to the changes in Go 1.26.",
                "content": "Go 1.26 introduces changes...",
            }
        ],
        "metadata": {"total_results": 1, "search_time_ms": 312},
    },
}


@pytest.mark.asyncio
async def test_general_search_response_mapping(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    data = await client.search("Go 1.26 release notes")
    assert data["results"][0]["title"] == "Go 1.26 Release Notes"
    assert data["metadata"]["total_results"] == 1


@pytest.mark.asyncio
async def test_anonymous_request_has_no_authorization_header(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient(api_key=None)
    assert client.is_anonymous is True
    await client.search("golang")
    assert "Authorization" not in _FakeSession.last_call["headers"]


@pytest.mark.asyncio
async def test_authenticated_request_sends_bearer_header(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient(api_key="super-secret-key")
    assert client.is_anonymous is False
    await client.search("golang")
    assert _FakeSession.last_call["headers"]["Authorization"] == "Bearer super-secret-key"


@pytest.mark.asyncio
async def test_client_identification_header_sent_on_anonymous_request(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient(api_key=None)
    await client.search("golang")
    assert _FakeSession.last_call["headers"]["X-Anysearch-Client"] == CLIENT_HEADER_VALUE


@pytest.mark.asyncio
async def test_client_identification_header_sent_on_authenticated_request(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient(api_key="super-secret-key")
    await client.search("golang")
    assert _FakeSession.last_call["headers"]["X-Anysearch-Client"] == CLIENT_HEADER_VALUE
    # the client-identification header itself never carries the API key
    assert "super-secret-key" not in _FakeSession.last_call["headers"]["X-Anysearch-Client"]


@pytest.mark.asyncio
async def test_api_key_never_appears_in_error_output(monkeypatch):
    error_envelope = {
        "code": -1,
        "message": "invalid request",
        "request_id": "x",
        "error_code": "bad_request",
    }
    _patch_session(monkeypatch, response=_FakeResponse(400, error_envelope))
    client = AnySearchClient(api_key="super-secret-key")
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "super-secret-key" not in str(excinfo.value)
    assert "super-secret-key" not in repr(excinfo.value)


@pytest.mark.asyncio
async def test_api_key_redacted_when_remote_server_echoes_it_back(monkeypatch):
    # A misconfigured or malicious remote/custom base_url endpoint could
    # echo the caller's own API key back inside its error `message`. That
    # text must never survive into the raised AnySearchError's str()/repr()
    # — the key is redacted before the exception is even constructed, and
    # the sanitized text (or equivalent safe wording) takes its place.
    error_envelope = {
        "code": -1,
        "message": "Authorization failed for Bearer super-secret-key",
        "request_id": "x",
        "error_code": "unauthorized",
    }
    _patch_session(monkeypatch, response=_FakeResponse(401, error_envelope))
    client = AnySearchClient(api_key="super-secret-key")
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "super-secret-key" not in str(excinfo.value)
    assert "super-secret-key" not in repr(excinfo.value)
    assert "[REDACTED]" in str(excinfo.value)


@pytest.mark.asyncio
async def test_anonymous_client_leaves_remote_message_unredacted_but_still_key_free(monkeypatch):
    # With no api_key configured there is nothing of the client's own to
    # redact; the (harmless, key-free) remote message passes through as-is
    # rather than being mangled.
    error_envelope = {
        "code": -1,
        "message": "rate limit exceeded",
        "request_id": "x",
        "error_code": "rate_limited",
    }
    _patch_session(monkeypatch, response=_FakeResponse(429, error_envelope))
    client = AnySearchClient(api_key=None)
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "rate limit exceeded" in str(excinfo.value)


@pytest.mark.asyncio
async def test_http_failure_raises_anysearch_error(monkeypatch):
    error_envelope = {"code": -1, "message": "internal error", "request_id": "x"}
    _patch_session(monkeypatch, response=_FakeResponse(500, error_envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("golang")


@pytest.mark.asyncio
async def test_timeout_raises_anysearch_error(monkeypatch):
    _patch_session(monkeypatch, exc=asyncio.TimeoutError())
    client = AnySearchClient(timeout=1)
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "timed out" in str(excinfo.value)


# --- strict positive finite timeout validation (AnySearchClient.__init__) ---


def test_timeout_missing_falls_back_to_default():
    # An omitted/missing timeout (None, e.g. from `config.get("timeout")`
    # on a plugin config with no explicit key) is the one case that still
    # falls back to a default rather than being rejected.
    from plugins._anysearch.helpers.anysearch_client import DEFAULT_TIMEOUT

    client = AnySearchClient(timeout=None)
    assert client.timeout == DEFAULT_TIMEOUT


def test_timeout_valid_integer_succeeds():
    client = AnySearchClient(timeout=20)
    assert client.timeout == 20.0


def test_timeout_valid_fractional_positive_succeeds():
    client = AnySearchClient(timeout=0.5)
    assert client.timeout == 0.5


def test_timeout_zero_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout=0)


def test_timeout_negative_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout=-5)


def test_timeout_nan_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout=math.nan)


def test_timeout_positive_infinity_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout=math.inf)


def test_timeout_negative_infinity_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout=-math.inf)


def test_timeout_non_numeric_raises():
    with pytest.raises(AnySearchError):
        AnySearchClient(timeout="not-a-number")


@pytest.mark.asyncio
async def test_client_connection_error_raises_anysearch_error(monkeypatch):
    _patch_session(monkeypatch, exc=aiohttp.ClientConnectionError("boom"))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("golang")


@pytest.mark.asyncio
async def test_malformed_json_response_raises_anysearch_error(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, raise_json=True))
    client = AnySearchClient()
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "non-JSON" in str(excinfo.value)


@pytest.mark.asyncio
async def test_response_missing_code_field_is_treated_as_error(monkeypatch):
    # A dict with no "code" key at all must not be silently treated as
    # success (previously `payload.get("code", 0)` defaulted a missing
    # field to 0, i.e. success). The body's own "message" is surfaced when
    # present, as with any other error envelope.
    envelope_without_code = {"message": "weird", "data": {"results": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope_without_code))
    client = AnySearchClient()
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "weird" in str(excinfo.value)


@pytest.mark.asyncio
async def test_response_missing_code_and_message_gets_explanatory_error(monkeypatch):
    envelope_without_code_or_message = {"data": {"results": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope_without_code_or_message))
    client = AnySearchClient()
    with pytest.raises(AnySearchError) as excinfo:
        await client.search("golang")
    assert "code" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_data_field_with_unexpected_shape_raises_anysearch_error(monkeypatch):
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": "not-an-object"}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("golang")


@pytest.mark.asyncio
async def test_empty_results_returns_empty_list(monkeypatch):
    envelope = {
        "code": 0,
        "message": "success",
        "request_id": "x",
        "data": {"results": [], "metadata": {"total_results": 0, "search_time_ms": 5}},
    }
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    data = await client.search("no such thing anywhere")
    assert data["results"] == []


@pytest.mark.asyncio
async def test_vertical_search_sends_tag_from_domain_and_qualified_sub_domain(monkeypatch):
    # get_sub_domains returns sub_domain values already fully qualified
    # (e.g. "finance.quote"); domain + sub_domain must NOT be concatenated
    # into "finance.finance.quote".
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    await client.search(
        "AAPL stock price",
        domain="finance",
        sub_domain="finance.quote",
        params={"symbol": "AAPL"},
    )
    body = _FakeSession.last_call["json"]
    assert body["tag"] == "finance.quote"
    assert body["params"] == {"symbol": "AAPL"}
    assert _FakeSession.last_call["method"] == "POST"
    assert _FakeSession.last_call["url"].endswith("/v1/search")


@pytest.mark.asyncio
async def test_vertical_search_accepts_direct_tag(monkeypatch):
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    await client.search("AAPL", tag="finance.quote")
    body = _FakeSession.last_call["json"]
    assert body["tag"] == "finance.quote"


@pytest.mark.asyncio
async def test_mismatched_domain_and_tag_fails_before_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("x", domain="finance", tag="legal.case")
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_domain_without_tag_or_sub_domain_fails_before_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("x", domain="finance")
    assert _FakeSession.last_call is None


def test_resolve_tag_direct_tag():
    assert resolve_tag(tag="finance.quote") == "finance.quote"


def test_resolve_tag_sub_domain_alias():
    assert resolve_tag(sub_domain="finance.quote") == "finance.quote"


def test_resolve_tag_domain_plus_qualified_sub_domain_no_double_prefix():
    assert resolve_tag(domain="finance", sub_domain="finance.quote") == "finance.quote"


def test_resolve_tag_conflicting_tag_and_sub_domain_raises():
    with pytest.raises(AnySearchError):
        resolve_tag(tag="finance.quote", sub_domain="legal.case")


def test_resolve_tag_domain_mismatch_raises():
    with pytest.raises(AnySearchError):
        resolve_tag(domain="finance", tag="legal.case")


def test_resolve_tag_domain_alone_raises():
    with pytest.raises(AnySearchError):
        resolve_tag(domain="finance")


def test_resolve_tag_none_returns_none():
    assert resolve_tag() is None


@pytest.mark.asyncio
async def test_sub_domain_discovery_request_shape(monkeypatch):
    envelope = {
        "code": 0,
        "message": "success",
        "request_id": "x",
        "data": {
            "domains": [
                {
                    "domain": "finance",
                    "description": "Financial data",
                    "sub_domains": [
                        {
                            "sub_domain": "finance.quote",
                            "description": "Stock quotes",
                            "params": {
                                "symbol": {"description": "Ticker", "required": True, "sort_order": 1},
                                "cn_code": {"description": "CN code", "required": False, "sort_order": 2},
                            },
                        }
                    ],
                }
            ]
        },
    }
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    data = await client.get_sub_domains(["finance", "code"])
    assert data["domains"][0]["domain"] == "finance"
    assert _FakeSession.last_call["method"] == "GET"
    assert _FakeSession.last_call["params"] == [("domain", "finance"), ("domain", "code")]


@pytest.mark.asyncio
async def test_get_sub_domains_one_domain_succeeds(monkeypatch):
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    await client.get_sub_domains(["finance"])
    assert _FakeSession.last_call is not None


@pytest.mark.asyncio
async def test_get_sub_domains_five_domains_succeeds(monkeypatch):
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    assert MAX_DOMAINS == 5
    await client.get_sub_domains(["a", "b", "c", "d", "e"])
    assert len(_FakeSession.last_call["params"]) == 5


@pytest.mark.asyncio
async def test_get_sub_domains_six_domains_fails_before_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.get_sub_domains(["a", "b", "c", "d", "e", "f"])
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_get_sub_domains_empty_domains_fails_before_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.get_sub_domains([])
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_get_sub_domains_dict_input_rejected_before_network_call(monkeypatch):
    # A dict must be rejected outright, not silently iterated as its keys
    # (Python's `list(some_dict)` yields the keys, which would otherwise
    # silently misinterpret a malformed call as a valid domain list).
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.get_sub_domains({"finance": "quote"})
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_get_sub_domains_non_string_items_rejected_before_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    envelope = {"code": 0, "message": "success", "request_id": "x", "data": {"domains": []}}
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.get_sub_domains(["finance", 42])
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_search_non_numeric_max_results_raises_instead_of_silently_clamping(monkeypatch):
    # A non-coercible max_results (e.g. a typo'd string) must be surfaced
    # as an error, not silently coerced down to the range floor (1) with
    # no indication the caller's input was malformed.
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    with pytest.raises(AnySearchError):
        await client.search("golang", max_results="ten")
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_extract_returns_url_title_content(monkeypatch):
    envelope = {
        "code": 0,
        "message": "success",
        "request_id": "x",
        "data": {
            "url": "https://example.com/article",
            "title": "Example Article",
            "content": "Extracted page content...",
        },
    }
    _patch_session(monkeypatch, response=_FakeResponse(200, envelope))
    client = AnySearchClient()
    data = await client.extract("https://example.com/article")
    assert data["title"] == "Example Article"
    assert _FakeSession.last_call["json"] == {"url": "https://example.com/article"}


@pytest.mark.asyncio
async def test_batch_search_ordering_and_partial_failure(monkeypatch):
    client = AnySearchClient()

    async def fake_search(query, **kwargs):
        if query == "fails":
            raise AnySearchError("simulated failure")
        return {"results": [{"title": query, "url": "u", "content": "c"}]}

    monkeypatch.setattr(client, "search", fake_search)

    results = await client.batch_search(
        [{"query": "first"}, {"query": "fails"}, {"query": "third"}]
    )

    assert [r["query"] for r in results] == ["first", "fails", "third"]
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert "simulated failure" in results[1]["error"]
    assert results[2]["ok"] is True


@pytest.mark.asyncio
async def test_batch_search_rejects_over_limit(monkeypatch):
    client = AnySearchClient()
    too_many = [{"query": f"q{i}"} for i in range(6)]
    with pytest.raises(AnySearchError):
        await client.batch_search(too_many, max_batch_size=5)


@pytest.mark.asyncio
async def test_batch_search_non_dict_item_isolated_without_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    results = await client.batch_search(["not-a-dict"])
    assert results[0]["ok"] is False
    assert "object" in results[0]["error"]
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_batch_search_missing_query_isolated_without_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    results = await client.batch_search([{"not_query": "x"}])
    assert results[0]["ok"] is False
    assert "query" in results[0]["error"]
    assert _FakeSession.last_call is None


@pytest.mark.asyncio
async def test_batch_search_blank_query_isolated_without_network_call(monkeypatch):
    _FakeSession.last_call = None  # reset shared class-level state from prior tests
    _patch_session(monkeypatch, response=_FakeResponse(200, SUCCESS_ENVELOPE))
    client = AnySearchClient()
    results = await client.batch_search([{"query": "   "}])
    assert results[0]["ok"] is False
    assert "empty" in results[0]["error"]
    assert _FakeSession.last_call is None
