import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import models
from helpers import extract_tools
from helpers import litellm_transport
from helpers.dirty_json import DirtyJson


@pytest.fixture(autouse=True)
def _clear_transport_capability_cache():
    litellm_transport.clear_transport_capability_cache()


def _chunk(content: str) -> dict:
    return {"choices": [{"delta": {"content": content}, "message": {}}]}


def _response_event(delta: str) -> dict:
    return {"type": "response.output_text.delta", "delta": delta}


class _AsyncChunkStream:
    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        self.index = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self.index]
        self.index += 1
        return chunk

    async def aclose(self):
        self.closed = True


class _FailingAsyncChunkStream:
    def __init__(self, exc: Exception):
        self.exc = exc
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise self.exc

    async def aclose(self):
        self.closed = True


class _DumpOnly:
    def __init__(self, **data):
        self._data = data

    def model_dump(self):
        return dict(self._data)


def test_extract_json_root_string_returns_canonical_snapshot():
    text = (
        'prefix {"tool_name":"response","tool_args":{"text":"brace } inside"}} '
        "trailing noise"
    )

    root = extract_tools.extract_json_root_string(text)

    assert root == '{"tool_name":"response","tool_args":{"text":"brace } inside"}}'
    assert extract_tools.json_parse_dirty(root)["tool_args"]["text"] == "brace } inside"
    assert extract_tools.extract_json_root_string(
        '{"tool_name":"response","tool_args":{"text":"missing"'
    ) is None
    assert extract_tools.extract_json_root_string('[{"tool_name":"response"}]') is None


@pytest.mark.parametrize(
    "content",
    [
        '{"tool_name":"response","tool_args":{"text":"partial"',
        'prefix {"tool_name":"response","tool_args":{}}',
        '[{"tool_name":"response","tool_args":{}}]',
        '```json\n{"tool_name":"response","tool_args":{}}\n```',
    ],
)
def test_extract_tool_request_skips_noncanonical_boundaries(monkeypatch, content):
    monkeypatch.setattr(
        extract_tools,
        "extract_json_root_string",
        lambda _content: pytest.fail("noncanonical content reached the root scanner"),
    )

    assert extract_tools.extract_tool_request(content) is None


def test_json_parse_dirty_prefers_valid_tool_request_after_preamble_object():
    text = (
        'I will call the tool after this note {"note":"not the tool"}.\n'
        '{"tool_name":"response","tool_args":{"text":"ok"}} trailing text'
    )

    assert extract_tools.json_parse_dirty(text) == {
        "tool_name": "response",
        "tool_args": {"text": "ok"},
    }


def test_extract_json_root_string_prefers_valid_tool_request():
    text = (
        'I will call the tool after this note {"note":"not the tool"}.\n'
        '{"tool_name":"response","tool_args":{"text":"ok"}} trailing text'
    )

    assert extract_tools.extract_json_root_string(text) == (
        '{"tool_name":"response","tool_args":{"text":"ok"}}'
    )
    assert extract_tools.extract_json_root_string(
        'Only a note {"note":"not the tool"}'
    ) == '{"note":"not the tool"}'


def test_extract_json_root_string_waits_for_complete_parallel_parent():
    partial = (
        '{"tool_name":"parallel","tool_args":{"tool_calls":['
        '{"tool_name":"code_execution_tool","tool_args":{"code":"first"}}'
    )

    assert extract_tools.extract_json_root_string(partial) is None

    full = (
        partial
        + ',{"tool_name":"code_execution_tool","tool_args":{"code":"second"}}'
        '],"wait":true}} trailing text'
    )

    root = extract_tools.extract_json_root_string(full)
    assert root == (
        '{"tool_name":"parallel","tool_args":{"tool_calls":['
        '{"tool_name":"code_execution_tool","tool_args":{"code":"first"}},'
        '{"tool_name":"code_execution_tool","tool_args":{"code":"second"}}'
        '],"wait":true}}'
    )
    parsed = extract_tools.json_parse_dirty(root)
    assert parsed["tool_name"] == "parallel"
    assert len(parsed["tool_args"]["tool_calls"]) == 2


def test_litellm_global_kwargs_merge_defaults_and_config(monkeypatch):
    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {"litellm_global_kwargs": {}},
    )

    assert models._merge_litellm_call_kwargs({})["drop_params"] is True
    assert models._merge_litellm_call_kwargs({"temperature": 0}) == {
        "drop_params": True,
        "temperature": 0,
    }

    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {
            "litellm_global_kwargs": {
                "drop_params": "false",
                "timeout": "30",
                "additional_drop_params": ["response_format"],
            }
        },
    )

    assert models._merge_litellm_call_kwargs({}) == {
        "drop_params": False,
        "timeout": 30,
        "additional_drop_params": ["response_format"],
    }

    original_drop_params = getattr(models.litellm, "drop_params", None)
    had_timeout = hasattr(models.litellm, "timeout")
    original_timeout = getattr(models.litellm, "timeout", None)
    had_additional_drop_params = hasattr(models.litellm, "additional_drop_params")
    original_additional_drop_params = getattr(
        models.litellm, "additional_drop_params", None
    )
    try:
        assert models.set_litellm_params() == {
            "drop_params": False,
            "timeout": 30,
            "additional_drop_params": ["response_format"],
        }
        assert models.litellm.drop_params is False
        if had_timeout:
            assert models.litellm.timeout == original_timeout
        else:
            assert not hasattr(models.litellm, "timeout")
        if had_additional_drop_params:
            assert (
                models.litellm.additional_drop_params
                == original_additional_drop_params
            )
        else:
            assert not hasattr(models.litellm, "additional_drop_params")
    finally:
        setattr(models.litellm, "drop_params", original_drop_params)
        if had_timeout:
            setattr(models.litellm, "timeout", original_timeout)
        elif hasattr(models.litellm, "timeout"):
            delattr(models.litellm, "timeout")
        if had_additional_drop_params:
            setattr(
                models.litellm,
                "additional_drop_params",
                original_additional_drop_params,
            )
        elif hasattr(models.litellm, "additional_drop_params"):
            delattr(models.litellm, "additional_drop_params")


def test_provider_defaults_do_not_freeze_litellm_global_kwargs(monkeypatch):
    monkeypatch.setattr(models, "get_provider_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(models, "get_api_key", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {"litellm_global_kwargs": {"drop_params": "true"}},
    )

    _, provider_kwargs = models._merge_provider_defaults("chat", "openai", {})

    assert "drop_params" not in provider_kwargs
    assert models._merge_litellm_call_kwargs(provider_kwargs)["drop_params"] is True

    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {"litellm_global_kwargs": {"drop_params": "false"}},
    )

    assert models._merge_litellm_call_kwargs(provider_kwargs)["drop_params"] is False


@pytest.mark.asyncio
async def test_unified_call_stops_chat_after_canonical_root_snapshot(monkeypatch):
    stream = _AsyncChunkStream(
        [
            _chunk('{"tool_name":"response","tool_args":{"text":"hello"}}'),
            _chunk(" unreachable"),
        ]
    )

    async def fake_acompletion(*args, **kwargs):
        assert kwargs["stream"] is True
        return stream

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)
    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {"litellm_global_kwargs": {}},
    )

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="chat",
    )

    seen: list[tuple[str, str]] = []

    async def response_callback(chunk: str, full: str):
        seen.append((chunk, full))
        return full.strip() if extract_tools.extract_tool_request(full) else None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == '{"tool_name":"response","tool_args":{"text":"hello"}}'
    assert reasoning == ""
    assert stream.index == 1
    assert stream.closed is True
    assert len(seen) == 1
    assert seen[0][1] == '{"tool_name":"response","tool_args":{"text":"hello"}}'


@pytest.mark.asyncio
async def test_unified_call_does_not_stop_for_embedded_tool_json(monkeypatch):
    stream = _AsyncChunkStream(
        [
            _chunk('Preamble {"note":"not the tool"}.\n'),
            _chunk(
                '{"tool_name":"response","tool_args":{"text":"ok"}} trailing text'
            ),
            _chunk(" unreachable"),
        ]
    )

    async def fake_acompletion(*args, **kwargs):
        assert kwargs["stream"] is True
        return stream

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)
    monkeypatch.setattr(
        models.settings,
        "get_settings",
        lambda: {"litellm_global_kwargs": {}},
    )

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="chat",
    )

    seen: list[tuple[str, str]] = []

    async def response_callback(chunk: str, full: str):
        seen.append((chunk, full))
        return full.strip() if extract_tools.extract_tool_request(full) else None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == (
        'Preamble {"note":"not the tool"}.\n'
        '{"tool_name":"response","tool_args":{"text":"ok"}} trailing text unreachable'
    )
    assert reasoning == ""
    assert stream.index == 3
    assert stream.closed is False
    assert len(seen) == 3
    assert seen[0][1] == 'Preamble {"note":"not the tool"}.\n'
    assert (
        seen[1][1]
        == 'Preamble {"note":"not the tool"}.\n'
        '{"tool_name":"response","tool_args":{"text":"ok"}} trailing text'
    )


@pytest.mark.asyncio
async def test_unified_call_closes_responses_stream_when_callback_raises(monkeypatch):
    stream = _AsyncChunkStream([_response_event("interrupt me")])

    class ExpectedIntervention(Exception):
        pass

    async def fake_aresponses(*args, **kwargs):
        assert kwargs["stream"] is True
        return stream

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        raise ExpectedIntervention()

    with pytest.raises(ExpectedIntervention):
        await wrapper.unified_call(
            messages=[],
            response_callback=response_callback,
        )

    assert stream.closed is True


@pytest.mark.asyncio
async def test_chat_completions_default_uses_acompletion(monkeypatch):
    stream = _AsyncChunkStream([_chunk("hello")])
    calls: list[str] = []

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        assert "a0_api_mode" not in kwargs
        return stream

    async def fake_aresponses(*args, **kwargs):
        raise AssertionError("Responses path should not be used")

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == "hello"
    assert reasoning == ""
    assert calls == ["chat"]


@pytest.mark.asyncio
async def test_unified_turn_stops_chat_stream_after_text_tool_request(monkeypatch):
    message = (
        '{"thoughts":["test"],"actions":['
        '{"tool_name":"response","tool_args":{"text":"ok"}}]}'
    )
    stream = _AsyncChunkStream([_chunk(message), _chunk(" unreachable")])

    async def fake_acompletion(*args, **kwargs):
        assert kwargs["stream"] is True
        return stream

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="chat",
    )

    async def response_callback(chunk: str, full: str):
        return full if extract_tools.extract_tool_request(full) else None

    result = await wrapper.unified_turn.__wrapped__(
        wrapper,
        messages=[],
        response_callback=response_callback,
    )

    assert result.response == message
    assert stream.index == 1
    assert stream.closed is True


@pytest.mark.asyncio
async def test_unified_call_retries_responses_with_high_reasoning(monkeypatch):
    validation_error = ValueError(
        "1 validation error for ResponseCreatedEvent\n"
        "response.reasoning.effort\n"
        "Input should be 'minimal', 'low', 'medium' or 'high' "
        "[type=literal_error, input_value='none', input_type=str]"
    )
    failing_stream = _FailingAsyncChunkStream(validation_error)
    working_stream = _AsyncChunkStream([_response_event("ok")])
    calls: list[dict] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return failing_stream
        return working_stream

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="gpt-5.4",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == "ok"
    assert reasoning == ""
    assert failing_stream.closed is True
    assert len(calls) == 2
    assert "reasoning" not in calls[0]
    assert calls[1]["reasoning"] == {"effort": "high"}


@pytest.mark.asyncio
async def test_unified_call_falls_back_to_chat_when_responses_endpoint_missing(
    monkeypatch,
):
    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        assert kwargs["input"][0]["content"] == "Native instructions"
        assert "responses_prompt_replacements" not in kwargs
        raise RuntimeError(
            "Client error '404 Not Found' for url "
            "'https://llm.agent-zero.ai/v1/responses'"
        )

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["messages"][0]["content"] == "Legacy instructions"
        assert "responses_prompt_replacements" not in kwargs
        assert kwargs["stream"] is True
        assert kwargs["drop_params"] is True
        assert "tool_choice" not in kwargs
        assert "parallel_tool_calls" not in kwargs
        return _AsyncChunkStream([_chunk("fallback")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="claude-opus-4.7",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
        a0_responses_function_tools=[{"type": "function", "name": "response", "parameters": {"type": "object"}}],
        responses_prompt_replacements={"Legacy instructions": "Native instructions"},
        tool_choice="auto",
        parallel_tool_calls=True,
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[SystemMessage(content="Legacy instructions")],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat"]

    response, reasoning = await wrapper.unified_call(
        messages=[SystemMessage(content="Legacy instructions")],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat", "chat"]


@pytest.mark.asyncio
async def test_unified_call_falls_back_when_litellm_hides_responses_404_url(
    monkeypatch,
):
    class NotFoundError(Exception):
        status_code = 404

    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        raise NotFoundError(
            'litellm.NotFoundError: NotFoundError: OpenAIException - {"detail":"Not Found"}'
        )

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        assert kwargs["drop_params"] is True
        return _AsyncChunkStream([_chunk("fallback")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="claude-opus-4.7",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat"]


@pytest.mark.parametrize(
    "responses_error",
    [
        "litellm.exceptions.APIError: Path /api/v1/responses is not "
        "available through this proxy.",
        "MaskedHTTPStatusError: Server error '500 Internal Server Error' "
        "for url 'https://api.venice.ai/api/v1/responses'",
        "InternalServerError: OpenAIException - '<=' not supported between "
        "instances of 'str' and 'int' for url 'http://192.168.200.52:4000/responses'",
        "ImportError Missing dependency No module named 'fastapi'. "
        "Run `pip install 'litellm[proxy]'`",
    ],
)
@pytest.mark.asyncio
async def test_unified_call_falls_back_for_proxy_responses_failures(
    monkeypatch,
    responses_error,
):
    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        raise RuntimeError(responses_error)

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        assert kwargs["drop_params"] is True
        return _AsyncChunkStream([_chunk("fallback")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat"]


@pytest.mark.asyncio
async def test_unified_call_falls_back_when_responses_mock_reads_sse_as_json(
    monkeypatch,
):
    calls: list[str] = []
    sse_error = json.JSONDecodeError(
        "Expecting value",
        'event: response.output_text.delta\ndata: {"delta":"hello"}\n\n',
        0,
    )
    failing_stream = _FailingAsyncChunkStream(sse_error)

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        return failing_stream

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        assert kwargs["drop_params"] is True
        return _AsyncChunkStream([_chunk("fallback")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="omniroute/test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat"]
    assert failing_stream.closed is True


@pytest.mark.asyncio
async def test_unified_call_falls_back_when_responses_bad_request_rejects_shape(
    monkeypatch,
):
    class BadRequestError(Exception):
        status_code = 400

    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        raise BadRequestError(
            'BadRequestError: Zod validation error: input_image Expected object, '
            'received string; Expected string, received array'
        )

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        assert kwargs["drop_params"] is True
        return _AsyncChunkStream([_chunk("fallback")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="venice-model",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "describe it"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.test/a.png"},
                    },
                ]
            )
        ],
        response_callback=response_callback,
    )

    assert response == "fallback"
    assert reasoning == ""
    assert calls == ["responses", "chat"]


@pytest.mark.asyncio
async def test_unified_call_raises_generic_responses_bad_request(monkeypatch):
    class BadRequestError(Exception):
        status_code = 400

    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        calls.append("responses")
        raise BadRequestError(
            "BadRequestError: validation error: invalid request: max_tokens is too high"
        )

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        raise AssertionError("generic 400 should not fallback to chat")

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    with pytest.raises(BadRequestError):
        await wrapper.unified_call(
            messages=[],
            response_callback=response_callback,
        )

    assert calls == ["responses"]


@pytest.mark.asyncio
async def test_unified_call_preserves_cache_control_with_chat_for_non_native_responses(
    monkeypatch,
):
    calls: list[str] = []

    async def fake_aresponses(*args, **kwargs):
        raise AssertionError("cache_control should keep Anthropic-family calls on chat")

    async def fake_acompletion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["stream"] is True
        messages = kwargs["messages"]
        assert "cache_control" not in messages[0]
        assert messages[0]["content"][-1]["cache_control"] == {
            "type": "ephemeral"
        }
        assert messages[1]["content"] == "question"
        assert messages[2]["content"][-1]["cache_control"] == {
            "type": "ephemeral"
        }
        assert messages[3]["content"] == "follow up"
        return _AsyncChunkStream([_chunk("cached")])

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "aresponses", fake_aresponses)
    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="claude-sonnet-4-5",
        provider="anthropic",
        model_config=None,
        a0_api_mode="responses",
    )

    async def response_callback(chunk: str, full: str):
        return None

    response, reasoning = await wrapper.unified_call(
        messages=[
            SystemMessage(content="static instructions"),
            HumanMessage(content="question"),
            AIMessage(content="previous answer"),
            HumanMessage(content="follow up"),
        ],
        response_callback=response_callback,
        explicit_caching=True,
    )

    assert response == "cached"
    assert reasoning == ""
    assert calls == ["chat"]


def test_responses_request_translates_messages_and_params():
    messages = [
        {"role": "system", "content": "You are precise."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Inspect this."},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.test/a.png"},
                },
            ],
        },
        {
            "role": "assistant",
            "content": "empty",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": '{"q":"a0"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "done"},
    ]
    kwargs = {
        "max_tokens": 42,
        "reasoning_effort": "high",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "schema": {"type": "object"},
                "strict": True,
            },
        },
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Search",
                    "parameters": {"type": "object"},
                    "strict": True,
                },
            }
        ],
    }

    request = litellm_transport.ResponsesTransport.from_chat(messages, kwargs)

    assert "instructions" not in request
    assert request["store"] is True
    assert request["max_output_tokens"] == 42
    assert request["reasoning"] == {"effort": "high"}
    assert request["text"] == {
        "format": {
            "type": "json_schema",
            "name": "answer",
            "schema": {"type": "object"},
            "strict": True,
        }
    }
    assert request["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Search",
            "parameters": {"type": "object", "properties": {}},
            "strict": True,
        }
    ]
    assert request["input"] == [
        {"role": "system", "content": "You are precise."},
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Inspect this."},
                {
                    "type": "input_image",
                    "image_url": "https://example.test/a.png",
                },
            ],
        },
        {
            "type": "function_call",
            "call_id": "call_1",
            "id": "call_1",
            "name": "lookup",
            "arguments": '{"q":"a0"}',
            "status": "completed",
        },
        {"type": "function_call_output", "call_id": "call_1", "output": "done"},
    ]


def test_responses_request_normalizes_reasoning_and_orphan_tool_choice():
    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {
            "reasoning_effort": "none",
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        },
    )

    assert "reasoning" not in request
    assert "tools" not in request
    assert "tool_choice" not in request
    assert "parallel_tool_calls" not in request

    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {"reasoning": {"effort": "xhigh"}},
    )

    assert request["reasoning"] == {"effort": "high"}

    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {"reasoning_effort": "off"},
    )

    assert "reasoning" not in request


def test_responses_request_normalizes_function_tool_parameter_shapes():
    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {
            "functions": [
                {
                    "name": "legacy_noop",
                    "description": "Legacy function",
                    "parameters": {},
                }
            ],
        },
    )

    assert request["tools"] == [
        {
            "type": "function",
            "name": "legacy_noop",
            "description": "Legacy function",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    ]

    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {
            "a0_responses_function_tools": [
                {
                    "type": "function",
                    "name": "native_noop",
                    "description": "Native function",
                    "parameters": {"type": "object"},
                }
            ],
            "responses_builtin_tools": [{"type": "web_search"}],
        },
    )

    assert request["tools"] == [
        {
            "type": "function",
            "name": "native_noop",
            "description": "Native function",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {"type": "web_search"},
    ]
    assert request["tool_choice"] == "required"
    assert request["parallel_tool_calls"] is False


def test_responses_request_preserves_explicit_a0_tool_controls():
    request = litellm_transport.ResponsesTransport.from_chat(
        [],
        {
            "a0_responses_function_tools": [
                {
                    "type": "function",
                    "name": "native_noop",
                    "parameters": {"type": "object"},
                }
            ],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        },
    )

    assert request["tool_choice"] == "auto"
    assert request["parallel_tool_calls"] is True


def test_chat_completions_kwargs_omit_empty_tools():
    kwargs = litellm_transport.ChatCompletionsTransport.prepare_kwargs(
        {
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "max_tokens": 8,
        }
    )

    assert kwargs == {"max_tokens": 8}

    kwargs = litellm_transport.ChatCompletionsTransport.prepare_kwargs(
        {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            "tool_choice": "auto",
        }
    )

    assert kwargs["tools"][0]["function"]["name"] == "lookup"
    assert kwargs["tool_choice"] == "auto"


def test_complete_falls_back_to_chat_when_responses_shim_sends_empty_tools(
    monkeypatch,
):
    calls: list[str] = []

    def fake_responses(*args, **kwargs):
        calls.append("responses")
        raise RuntimeError(
            "Value error, `tools` must not be an empty array. "
            "Either provide at least one tool or omit the field entirely."
        )

    def fake_completion(*args, **kwargs):
        calls.append("chat")
        assert kwargs["drop_params"] is True
        assert "tools" not in kwargs
        assert "tool_choice" not in kwargs
        assert "parallel_tool_calls" not in kwargs
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(litellm_transport, "responses", fake_responses)
    monkeypatch.setattr(litellm_transport, "completion", fake_completion)

    transport = litellm_transport.LiteLLMTransport(
        model="hosted_vllm/qwen",
        messages=[{"role": "user", "content": "hi"}],
        kwargs={
            "a0_api_mode": "responses",
            "tools": [],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "max_tokens": 8,
        },
    )

    parsed = transport.complete()

    assert parsed["response_delta"] == "ok"
    assert calls == ["responses", "chat"]


def test_responses_request_adds_openai_prompt_cache_key_for_static_prefix():
    request = litellm_transport.ResponsesTransport.from_chat(
        [
            {"role": "system", "content": "stable system prompt"},
            {"role": "user", "content": "dynamic question"},
        ],
        {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Search",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        },
        model="openai/gpt-5.4",
    )

    assert request["prompt_cache_key"].startswith("a0-")
    assert len(request["prompt_cache_key"]) == 35
    assert "stable system prompt" not in request["prompt_cache_key"]

    request_again = litellm_transport.ResponsesTransport.from_chat(
        [
            {"role": "system", "content": "stable system prompt"},
            {"role": "user", "content": "different dynamic question"},
        ],
        {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Search",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        },
        model="openai/gpt-5.4",
    )

    assert request_again["prompt_cache_key"] == request["prompt_cache_key"]


def test_responses_request_respects_explicit_prompt_cache_and_retention():
    request = litellm_transport.ResponsesTransport.from_chat(
        [{"role": "system", "content": "stable system prompt"}],
        {
            "prompt_cache_key": "user-provided-key",
            "prompt_cache_retention": "24h",
            "extra_body": {"prompt_cache_retention": "in_memory"},
        },
        model="openai/gpt-5.4",
    )

    assert request["prompt_cache_key"] == "user-provided-key"
    assert "prompt_cache_retention" not in request
    assert request["extra_body"]["prompt_cache_retention"] == "in_memory"


def test_responses_request_adds_azure_prompt_cache_params():
    request = litellm_transport.ResponsesTransport.from_chat(
        [{"role": "system", "content": "stable system prompt"}],
        {"prompt_cache_retention": "24h"},
        model="azure/gpt-4.1",
    )

    assert request["prompt_cache_key"].startswith("a0-")
    assert "prompt_cache_retention" not in request
    assert request["extra_body"]["prompt_cache_retention"] == "24h"


def test_responses_request_does_not_add_openai_cache_key_to_custom_api_base():
    request = litellm_transport.ResponsesTransport.from_chat(
        [{"role": "system", "content": "stable system prompt"}],
        {"api_base": "https://llm.agent-zero.ai/v1"},
        model="openai/gpt-5.4",
    )

    assert "prompt_cache_key" not in request


def test_chat_kwargs_add_openai_prompt_cache_key_for_chat_completions():
    kwargs = litellm_transport.ChatCompletionsTransport.prepare_kwargs(
        {"max_tokens": 10},
        model="openai/gpt-5.4",
        messages=[
            {"role": "system", "content": "stable system prompt"},
            {"role": "user", "content": "dynamic question"},
        ],
    )

    assert kwargs["prompt_cache_key"].startswith("a0-")
    assert kwargs["max_tokens"] == 10


@pytest.mark.parametrize("model,mode,expected", [
    ("openai/gpt-5.4", "auto", "prompt_cache_key"),
    ("anthropic/claude-sonnet-4-5", "auto", "cache_control"),
    ("openai/custom", "auto", "off"),
    ("openai/custom", "prompt_cache_key", "prompt_cache_key"),
    ("openai/custom", "cache_control", "cache_control"),
    ("openai/gpt-5.4", "off", "off"),
    ("anthropic/claude-sonnet-4-5", "off", "off"),
])
def test_prompt_cache_mode_controls_hints_without_mutating_callers(model, mode, expected):
    from copy import deepcopy

    messages = [{"role": "system", "content": "Stable instructions"},
                {"role": "user", "content": "Question"}]
    kwargs = {"a0_prompt_cache_mode": mode, "a0_explicit_prompt_caching": True}
    if model == "openai/custom":
        kwargs["api_base"] = "https://custom.example/v1"
    original = deepcopy((messages, kwargs))
    request = litellm_transport.LiteLLMTransport(
        model=model, messages=messages, kwargs=kwargs
    )._chat_request(stream=False)

    assert (messages, kwargs) == original
    assert ("prompt_cache_key" in request) == (expected == "prompt_cache_key")
    assert litellm_transport._has_cache_control(request["messages"]) == (expected == "cache_control")
    assert "a0_prompt_cache_mode" not in request


@pytest.mark.parametrize("value", [False, "", "typo"])
def test_invalid_prompt_cache_mode_fails_before_provider_call(value):
    with pytest.raises(ValueError, match="a0_prompt_cache_mode must be"):
        litellm_transport.ChatCompletionsTransport.prepare_kwargs(
            {"a0_prompt_cache_mode": value}, model="openai/custom"
        )


def test_custom_cache_control_override_keeps_markers_on_chat():
    transport = litellm_transport.LiteLLMTransport(
        model="openai/custom",
        messages=[{"role": "system", "content": "Stable instructions"}],
        kwargs={"api_base": "https://custom.example/v1", "a0_api_mode": "responses",
                "a0_prompt_cache_mode": "cache_control", "a0_explicit_prompt_caching": True},
    )
    assert transport.policy.mode is litellm_transport.TransportMode.CHAT_COMPLETIONS
    assert litellm_transport._has_cache_control(transport._chat_request(stream=False)["messages"])


@pytest.mark.parametrize("mode", ["prompt_cache_key", "off"])
def test_responses_cache_mode_preserves_explicit_retention(mode):
    request = litellm_transport.ResponsesTransport.from_chat(
        [{"role": "system", "content": "Stable instructions"}],
        {"a0_prompt_cache_mode": mode, "prompt_cache_retention": "24h"},
        model="openai/gpt-5.4",
    )
    assert ("prompt_cache_key" in request) == (mode == "prompt_cache_key")
    assert request["extra_body"]["prompt_cache_retention"] == "24h"
    assert "a0_prompt_cache_mode" not in request


@pytest.mark.parametrize("key_kwargs", [
    {"prompt_cache_key": "caller-key"},
    {"extra_body": {"prompt_cache_key": "caller-key"}},
])
def test_prompt_cache_mode_preserves_explicit_keys_on_both_transports(key_kwargs):
    messages = [{"role": "system", "content": "Stable instructions"}]
    kwargs = {"api_base": "https://custom.example/v1",
              "a0_prompt_cache_mode": "prompt_cache_key", **key_kwargs}
    for prepare in (litellm_transport.ChatCompletionsTransport.prepare_kwargs,
                    litellm_transport.ResponsesTransport.prepare_kwargs):
        request = prepare(kwargs, model="openai/custom", messages=messages)
        assert request.get("prompt_cache_key") == key_kwargs.get("prompt_cache_key")
        assert request.get("extra_body", {}).get("prompt_cache_key") == key_kwargs.get("extra_body", {}).get("prompt_cache_key")
        assert "a0_prompt_cache_mode" not in request


def test_chat_messages_strip_cache_control_for_openai_prompt_cache():
    messages = [
        {
            "role": "system",
            "cache_control": {"type": "ephemeral"},
            "content": [
                {
                    "type": "text",
                    "text": "stable system prompt",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    prepared = litellm_transport.ChatCompletionsTransport.prepare_messages(
        messages,
        model="openai/gpt-5.4",
        kwargs={},
    )

    assert "cache_control" not in prepared[0]
    assert "cache_control" not in prepared[0]["content"][0]
    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_chat_kwargs_mark_cached_tools_for_cache_control_providers():
    kwargs = litellm_transport.ChatCompletionsTransport.prepare_kwargs(
        {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Search",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        },
        model="anthropic/claude-sonnet-4-5",
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "static instructions",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
        explicit_prompt_caching=True,
    )

    assert kwargs["tools"][0]["function"]["cache_control"] == {
        "type": "ephemeral"
    }


@pytest.mark.parametrize("content", [
    None, "", [],
    [{"type": "thinking", "thinking": "Plan", "signature": "signature"}],
    [{"type": "redacted_thinking", "data": "opaque"}],
])
def test_cache_markers_preserve_assistant_tool_calls_without_cacheable_text(content):
    messages = [
        {"role": "system", "content": "Instructions"},
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Previous answer"},
        {
            "role": "assistant", "content": content,
            "tool_calls": [{"id": "call_1", "type": "function", "function": {
                "name": "lookup", "arguments": "{}",
            }}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "Result"},
        {"role": "user", "content": "Current extras"},
    ]

    prepared = litellm_transport.apply_chat_prompt_cache_markers(
        messages, model="anthropic/claude-sonnet-4-5"
    )

    assert prepared[3] == messages[3]
    assert prepared[4:] == messages[4:]
    assert [i for i, message in enumerate(prepared)
            if litellm_transport._has_cache_control(message)] == [0, 2]


def test_chat_kwargs_strip_orphan_tool_choice_and_enable_fallback_drop_params():
    kwargs = litellm_transport.ChatCompletionsTransport.prepare_kwargs(
        {
            "tool_choice": "auto",
            "parallel_tool_calls": True,
            "max_tokens": 10,
        },
        fallback_error=RuntimeError("This model does not support Responses API"),
    )

    assert kwargs["max_tokens"] == 10
    assert kwargs["drop_params"] is True
    assert "tool_choice" not in kwargs
    assert "parallel_tool_calls" not in kwargs


def test_cache_control_policy_keeps_native_responses_first():
    messages = [
        {
            "role": "system",
            "content": "static instructions",
            "cache_control": {"type": "ephemeral"},
        }
    ]

    openai_policy = litellm_transport.TransportPolicy.from_request(
        "openai/gpt-5.4",
        {"a0_api_mode": "responses"},
        messages=messages,
    )
    anthropic_policy = litellm_transport.TransportPolicy.from_request(
        "anthropic/claude-sonnet-4-5",
        {"a0_api_mode": "responses"},
        messages=messages,
    )

    assert openai_policy.mode is litellm_transport.TransportMode.RESPONSES
    assert anthropic_policy.mode is litellm_transport.TransportMode.CHAT_COMPLETIONS


def test_responses_fallback_does_not_mask_rate_limits():
    exc = RuntimeError(
        "RateLimitError: 429 Too Many Requests for url "
        "https://provider.example/v1/responses"
    )

    policy = litellm_transport.TransportPolicy(
        mode=litellm_transport.TransportMode.RESPONSES
    )

    assert (
        policy.recover(exc, got_any_chunk=False)
        is litellm_transport.TransportRecovery.RAISE
    )


def test_responses_fallback_on_untyped_input_item_rejection():
    class BadRequestError(RuntimeError):
        status_code = 400

    policy = litellm_transport.TransportPolicy(
        mode=litellm_transport.TransportMode.RESPONSES
    )

    assert policy.recover(
        BadRequestError("Cannot determine type of item"), got_any_chunk=False
    ) is litellm_transport.TransportRecovery.FALLBACK_TO_CHAT
    assert policy.mode is litellm_transport.TransportMode.CHAT_COMPLETIONS


@pytest.mark.parametrize("source", ["delta", "message"])
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"reasoning_content": "legacy"}, "legacy"),
        ({"reasoning": "fallback"}, "fallback"),
        ({"reasoning_content": "legacy", "reasoning": "fallback"}, "legacy"),
        ({"reasoning_content": "", "reasoning": "fallback"}, "fallback"),
        ({"reasoning": "summary__ENCRYPTED_REASONING__opaque"}, "summary"),
        ({}, ""),
    ],
)
def test_chat_reasoning_field_fallback(source, fields, expected):
    parsed = litellm_transport.ChatCompletionsTransport.parse(
        {"choices": [{source: {"content": "answer", **fields}}]}
    )

    assert parsed == {"reasoning_delta": expected, "response_delta": "answer"}


def test_responses_response_parser_extracts_text_reasoning_and_function_calls():
    text_response = {
        "output": [
            {"type": "reasoning", "summary": [{"text": "because"}]},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "answer"}],
            },
        ]
    }

    parsed = litellm_transport.ResponsesTransport.parse_response(text_response)

    assert parsed == {"response_delta": "answer", "reasoning_delta": "because"}

    tool_response = {
        "output": [
            {
                "type": "function_call",
                "name": "lookup",
                "arguments": '{"q":"a0"}',
            }
        ]
    }

    parsed_tool = litellm_transport.ResponsesTransport.parse_response(tool_response)

    assert extract_tools.json_parse_dirty(parsed_tool["response_delta"]) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }


@pytest.mark.parametrize("commentary", [None, "Looking it up."])
def test_chat_completions_response_parser_extracts_tool_calls(commentary):
    parsed = litellm_transport.ChatCompletionsTransport.parse(
        {
            "choices": [
                {
                    "message": {
                        "content": commentary,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"q":"a0"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert extract_tools.json_parse_dirty(parsed["response_delta"]) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }
    items = parsed["_output_items"]
    assert items[-1]["name"] == "lookup"
    assert items[-1]["call_id"] == "call_1"
    if commentary:
        assert items[0] == {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": commentary}],
        }
    else:
        assert len(items) == 1


def test_chat_completions_stream_parser_accumulates_tool_call_arguments():
    parser = litellm_transport.ChatCompletionsStreamParser()

    assert parser.parse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"q":',
                                },
                            }
                        ]
                    }
                }
            ]
        }
    ) == {"reasoning_delta": "", "response_delta": ""}
    parsed = parser.parse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": '"a0"}'},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )

    assert extract_tools.json_parse_dirty(parsed["response_delta"]) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }
    assert parser.output_items()[0]["name"] == "lookup"
    assert parser.flush() == {"reasoning_delta": "", "response_delta": ""}


def test_chat_completions_stream_parser_reads_dumped_tool_calls():
    parser = litellm_transport.ChatCompletionsStreamParser()

    assert parser.parse(
        _DumpOnly(
            choices=[
                _DumpOnly(
                    delta=_DumpOnly(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": _DumpOnly(
                                    name="lookup",
                                    arguments='{"q":"a0"}',
                                ),
                            }
                        ]
                    )
                )
            ]
        )
    ) == {"reasoning_delta": "", "response_delta": ""}

    parsed = parser.parse(
        _DumpOnly(choices=[_DumpOnly(delta=_DumpOnly(), finish_reason="tool_calls")])
    )

    assert extract_tools.json_parse_dirty(parsed["response_delta"]) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }


def test_chat_completions_stream_parser_preserves_optional_usage():
    parser = litellm_transport.ChatCompletionsStreamParser()
    parser.parse(
        {
            "choices": [],
            "usage": {"prompt_tokens": 240},
            "_hidden_params": {"response_cost": 0.0084},
        }
    )
    parser.parse(
        {
            "choices": [],
            "usage": {"completion_tokens": 16, "total_tokens": 256},
        }
    )
    transport = litellm_transport.LiteLLMTransport(
        model="custom/model",
        messages=[{"role": "user", "content": "question"}],
        kwargs={"a0_api_mode": "chat_completions"},
    )

    result = transport._stream_result_from_chat_parser(parser)

    assert result is not None
    assert result.usage == {
        "prompt_tokens": 240,
        "completion_tokens": 16,
        "total_tokens": 256,
        "cost": 0.0084,
    }


@pytest.mark.asyncio
async def test_unified_turn_preserves_chat_streaming_tool_calls(monkeypatch):
    async def fake_acompletion(*args, **kwargs):
        return _AsyncChunkStream(
            [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "lookup",
                                            "arguments": '{"q":',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {"arguments": '"a0"}'},
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
            ]
        )

    async def fake_rate_limiter(*args, **kwargs):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", fake_acompletion)
    monkeypatch.setattr(models, "apply_rate_limiter", fake_rate_limiter)

    wrapper = models.LiteLLMChatWrapper(
        model="test-model",
        provider="openai",
        model_config=None,
    )

    async def response_callback(chunk: str, full: str):
        return None

    result = await wrapper.unified_turn(
        messages=[],
        response_callback=response_callback,
        a0_api_mode="chat",
    )

    assert extract_tools.json_parse_dirty(result.response) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }
    assert result.function_calls[0].name == "lookup"
    assert result.function_calls[0].arguments == {"q": "a0"}


def test_responses_stream_parser_accumulates_function_call_arguments():
    parser = litellm_transport.ResponsesEventParser()

    assert parser.parse(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": "",
            },
        }
    ) == {"reasoning_delta": "", "response_delta": ""}
    partial = parser.parse(
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_1",
            "output_index": 0,
            "delta": '{"q":',
        }
    )
    assert partial["response_delta"] == '{"tool_name":"lookup","tool_args":{"q":'

    parsed = parser.parse(
        {
            "type": "response.function_call_arguments.done",
            "item_id": "fc_1",
            "output_index": 0,
            "name": "lookup",
            "arguments": '{"q":"a0"}',
        }
    )

    assert extract_tools.json_parse_dirty(partial["response_delta"] + parsed["response_delta"]) == {
        "tool_name": "lookup",
        "tool_args": {"q": "a0"},
    }
    assert parser.parse(
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": '{"q":"a0"}',
            },
        }
    ) == {"reasoning_delta": "", "response_delta": ""}


def test_responses_stream_parser_streams_response_function_arguments():
    parser = litellm_transport.ResponsesEventParser()

    parser.parse(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "name": "response",
                "arguments": "",
            },
        }
    )
    chunks = [
        parser.parse(
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_1",
                "delta": '{"text":"Hello',
            }
        )["response_delta"],
        parser.parse(
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_1",
                "delta": ' world"}',
            }
        )["response_delta"],
        parser.parse(
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc_1",
                "name": "response",
                "arguments": '{"text":"Hello world"}',
            }
        )["response_delta"],
    ]

    assert chunks[0] == '{"tool_name":"response","tool_args":{"text":"Hello'
    assert DirtyJson.parse_string(chunks[0]) == {
        "tool_name": "response",
        "tool_args": {"text": "Hello"},
    }
    assert extract_tools.json_parse_dirty("".join(chunks)) == {
        "tool_name": "response",
        "tool_args": {"text": "Hello world"},
    }
    assert chunks[-1] == "}"
    assert parser.parse(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "name": "response",
                "arguments": '{"text":"Hello world"}',
            },
        }
    ) == {"reasoning_delta": "", "response_delta": ""}


def test_responses_stream_parser_uses_completed_response_when_no_deltas_arrive():
    parser = litellm_transport.ResponsesEventParser()

    parsed = parser.parse(
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "done"}],
                    }
                ]
            },
        }
    )

    assert parsed == {"reasoning_delta": "", "response_delta": "done"}


def test_responses_stream_parser_handles_refusal_and_failed_events():
    parser = litellm_transport.ResponsesEventParser()

    assert parser.parse(
        {"type": "response.refusal.delta", "delta": "no"}
    ) == {"reasoning_delta": "", "response_delta": "no"}

    with pytest.raises(RuntimeError, match="policy"):
        parser.parse(
            {
                "type": "response.failed",
                "response": {"error": {"message": "policy"}},
            }
        )


def test_responses_response_parser_groups_parallel_function_calls():
    response = {
        "output": [
            {
                "type": "function_call",
                "name": "lookup",
                "arguments": '{"q":"a0"}',
            },
            {
                "type": "function_call",
                "name": "rank",
                "arguments": '{"limit":2}',
            },
        ]
    }

    parsed = litellm_transport.ResponsesTransport.parse_response(response)

    assert extract_tools.json_parse_dirty(parsed["response_delta"]) == {
        "tool_name": "parallel_tool_calls",
        "tool_args": {
            "calls": [
                {"tool_name": "lookup", "tool_args": {"q": "a0"}},
                {"tool_name": "rank", "tool_args": {"limit": 2}},
            ]
        },
    }


def test_responses_stream_parser_preserves_non_ascii_function_call_arguments():
    parser = litellm_transport.ResponsesEventParser()

    parser.parse(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "function_call",
                "id": "fc_1",
                "name": "response",
                "arguments": "",
            },
        }
    )
    parsed = parser.parse(
        {
            "type": "response.function_call_arguments.done",
            "item_id": "fc_1",
            "name": "response",
            "arguments": '{"text":"привет"}',
        }
    )

    assert parsed["response_delta"] == '{"tool_name": "response", "tool_args": {"text": "привет"}}'


@pytest.mark.asyncio
async def test_native_argument_progress_keeps_interleaved_calls_and_terminal_metadata(monkeypatch):
    arguments = '{"runtime":"python","code":"print(\\"日本\\")","nested":{"items":[1,2]}}'
    first = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "code_execution_tool", "arguments": arguments}
    second = {"type": "function_call", "id": "fc_2", "call_id": "call_2", "name": "lookup", "arguments": '{"q":"a0"}'}
    split = arguments.index('日本')
    events = [
        {"type": "response.output_item.added", "item": {**first, "arguments": ""}},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": arguments[:split]},
        {"type": "response.output_item.added", "item": {**second, "arguments": ""}},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_2", "delta": second["arguments"]},
        {"type": "response.output_item.done", "item": second},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": arguments[split:]},
        {"type": "response.output_item.done", "item": first},
        {"type": "response.completed", "response": {"id": "resp_1", "output": [first, second], "usage": {"input_tokens": 2048}}},
    ]
    stream = _AsyncChunkStream(events)

    async def aresponses(**kwargs):
        return stream

    async def no_limiter(*args, **kwargs):
        return None

    snapshots = []

    async def callback(chunk, full):
        snapshots.append((stream.index, full))
        return full  # Native turns must still consume completion metadata.

    monkeypatch.setattr(litellm_transport, "aresponses", aresponses)
    monkeypatch.setattr(models, "apply_rate_limiter", no_limiter)
    wrapper = models.LiteLLMChatWrapper(model="test-model", provider="openai", model_config=None)
    result = await wrapper.unified_turn(messages=[], response_callback=callback, a0_api_mode="responses")

    assert snapshots[0][0] == 2
    assert DirtyJson.parse_string(snapshots[0][1])["tool_args"]["runtime"] == "python"
    roots = extract_tools.extract_json_root_strings(snapshots[-1][1])
    assert [json.loads(root)["tool_name"] for root in roots] == ["code_execution_tool", "lookup"]
    assert json.loads(roots[0])["tool_args"] == json.loads(arguments)
    assert [call.call_id for call in result.function_calls] == ["call_1", "call_2"]
    assert result.usage == {"input_tokens": 2048}
    assert stream.index == len(events)


@pytest.mark.asyncio
@pytest.mark.parametrize("incomplete", [False, True])
async def test_interrupted_native_argument_stream_cannot_become_a_text_tool(monkeypatch, incomplete):
    events = [
        {"type": "response.output_item.added", "item": {"type": "function_call", "id": "fc_1", "name": "lookup", "arguments": ""}},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": '{"q":"partial'},
    ]
    if incomplete:
        events.append({"type": "response.incomplete", "response": {"status": "incomplete"}})
    stream = _AsyncChunkStream(events)

    async def aresponses(**kwargs):
        return stream

    monkeypatch.setattr(litellm_transport, "aresponses", aresponses)
    transport = litellm_transport.LiteLLMTransport(model="openai/test", messages=[], kwargs={"a0_api_mode": "responses"})
    with pytest.raises(RuntimeError, match="incomplete|before native tool calls completed"):
        async for _ in transport.astream():
            pass
    assert transport.last_result is None
    assert stream.closed


def test_stream_metadata_recovers_reasoning_and_partial_terminal_call_lists():
    parser = litellm_transport.ResponsesEventParser()
    reasoning = {"type": "reasoning", "id": "rs_1", "encrypted_content": "encrypted", "summary": []}
    first = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "lookup", "arguments": '{"q":"first"}'}
    second = {"type": "function_call", "id": "fc_2", "call_id": "call_2", "name": "lookup", "arguments": '{"q":"second"}'}
    for index, item in reversed(list(enumerate([reasoning, first, second]))):
        parser.parse({"type": "response.output_item.done", "output_index": index, "item": item})
    terminal = {"id": "resp_1", "output": [{**second, "status": "completed"}]}
    parser.parse({"type": "response.completed", "response": terminal})
    assert parser.finish() == parser.finish()
    assert terminal == {"id": "resp_1", "output": [{**second, "status": "completed"}]}
    transport = litellm_transport.LiteLLMTransport(model="openai/test", messages=[], kwargs={"a0_api_mode": "responses"})
    result = transport._stream_result_from_parser(parser, {})
    assert [item.to_dict() for item in result.output_items] == [reasoning, first, {**second, "status": "completed"}]
    assert [call.call_id for call in result.function_calls] == ["call_1", "call_2"]


def test_terminal_reasoning_null_does_not_erase_streamed_ciphertext():
    parser = litellm_transport.ResponsesEventParser()
    reasoning = {"type": "reasoning", "id": "rs_1", "encrypted_content": "encrypted", "summary": []}
    parser.parse({"type": "response.output_item.done", "output_index": 0, "item": reasoning})
    parser.parse({"type": "response.completed", "response": {"output": [{**reasoning, "encrypted_content": None}]}})
    transport = litellm_transport.LiteLLMTransport(model="openai/test", messages=[], kwargs={"a0_api_mode": "responses"})
    result = transport._stream_result_from_parser(parser, {})
    assert [item.to_dict() for item in result.output_items] == [reasoning]


def test_unidentified_stream_fragment_cannot_duplicate_terminal_call():
    parser = litellm_transport.ResponsesEventParser()
    item = {"type": "function_call", "name": "lookup", "arguments": '{"q":"a0"}'}
    parser.parse({"type": "response.output_item.done", "output_index": 0, "item": item})
    parser.parse({"type": "response.completed", "response": {"output": [item]}})
    transport = litellm_transport.LiteLLMTransport(model="openai/test", messages=[], kwargs={"a0_api_mode": "responses"})
    result = transport._stream_result_from_parser(parser, {})
    assert len(result.function_calls) == 1
