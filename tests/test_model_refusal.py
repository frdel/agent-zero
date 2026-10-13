import pytest
from litellm import ContentPolicyViolationError

import models
from helpers import litellm_transport
from helpers import extract_tools
from helpers.llm_result import LLMResult
from helpers.litellm_transport import ChatCompletionsStreamParser, ChatCompletionsTransport


@pytest.mark.parametrize("reason", ["content_filter", "refusal"])
def test_refusals_fail_before_partial_tool_calls_can_be_returned(reason):
    raw = {"model": "test", "choices": [{"finish_reason": reason, "message": {
        "content": "partial", "tool_calls": [{"type": "function", "function": {
            "name": "response", "arguments": '{"text":"partial"}',
        }}],
    }}]}
    for parse in (ChatCompletionsTransport.parse, ChatCompletionsStreamParser().parse):
        with pytest.raises(ContentPolicyViolationError, match=f"finish_reason={reason}"):
            parse(raw)
    assert ChatCompletionsTransport.parse({"choices": [{"finish_reason": "stop"}]}) == {
        "response_delta": "", "reasoning_delta": "",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_refusal_stops_model_call_without_retry_and_closes_stream(monkeypatch, stream):
    calls = 0
    closed = False
    raw = {"model": "test", "choices": [{"finish_reason": "content_filter", "delta": {}}]}

    async def chunks():
        nonlocal closed
        try:
            yield raw
        finally:
            closed = True

    async def completion(**kwargs):
        nonlocal calls
        calls += 1
        return chunks() if kwargs["stream"] else raw

    async def callback(*args):
        raise AssertionError("Refused output must not reach callbacks")

    monkeypatch.setattr(litellm_transport, "acompletion", completion)
    wrapper = models.LiteLLMChatWrapper(model="test", provider="openai")
    with pytest.raises(ContentPolicyViolationError, match="Model provider refused"):
        await wrapper.unified_turn.__wrapped__(
            wrapper, messages=[], response_callback=callback if stream else None,
        )
    assert calls == 1
    assert closed == stream


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_length_finish_reason_is_recorded_as_truncation(monkeypatch, stream):
    partial = '{"thoughts":["planning"],"tool_name":"response","tool_args":{"text":"cut'
    raw = {"model": "test", "choices": [{"finish_reason": "length", "message": {"content": partial}}]}
    chunks_raw = [
        {"model": "test", "choices": [{"finish_reason": None, "delta": {"content": partial}}]},
        {"model": "test", "choices": [{"finish_reason": "length", "delta": {}}]},
    ]

    async def chunks():
        for chunk in chunks_raw:
            yield chunk

    async def completion(**kwargs):
        return chunks() if kwargs["stream"] else raw

    async def callback(*args):
        return None

    monkeypatch.setattr(litellm_transport, "acompletion", completion)
    wrapper = models.LiteLLMChatWrapper(model="test", provider="openai")
    result = await wrapper.unified_turn.__wrapped__(
        wrapper, messages=[], response_callback=callback if stream else None,
    )
    assert result.response == partial
    assert result.finish_reason == "length"
    assert result.truncated is True


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["length", "max_tokens", "tool_calls"])
@pytest.mark.parametrize("arguments", ['{"text":"cut', '{"text":"done"}'])
async def test_native_chat_finish_metadata_survives_callback_stop(monkeypatch, finish_reason, arguments):
    async def chunks():
        yield {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_cut", "type": "function",
             "function": {"name": "response", "arguments": arguments}},
        ]}, "finish_reason": None}]}
        yield {"choices": [{"delta": {}, "finish_reason": finish_reason}]}

    async def completion(**kwargs):
        return chunks()

    async def callback(chunk, full):
        return full if extract_tools.extract_tool_request(full) is not None else None

    monkeypatch.setattr(litellm_transport, "acompletion", completion)
    wrapper = models.LiteLLMChatWrapper(model="test", provider="openai")
    result = await wrapper.unified_turn.__wrapped__(
        wrapper, messages=[], response_callback=callback,
    )

    assert result.finish_reason == finish_reason
    assert result.function_calls[0].call_id == "call_cut"
    assert result.function_calls[0].raw["arguments"] == arguments


@pytest.mark.parametrize("finish_reason", ["length", "max_tokens", "stop"])
def test_finish_reason_roundtrips_without_persisting_in_history(finish_reason):
    result = LLMResult.from_chat(response="cut", finish_reason=finish_reason)
    result.history_extras = "current extras"

    assert LLMResult.from_dict(result.to_dict()) == result
    assert result.truncated is (finish_reason != "stop")
    assert "finish_reason" not in result.metadata()["responses"]
    assert LLMResult.from_dict({"response": "legacy"}).finish_reason == ""
