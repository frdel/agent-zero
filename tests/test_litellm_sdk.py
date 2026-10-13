"""Exercise the installed SDK over loopback HTTP, without provider credentials."""

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from types import SimpleNamespace

import pytest

import models
from helpers.litellm_transport import (
    LiteLLMTransport,
    clear_transport_capability_cache,
    delete_stored_response_ids,
)


TOOL = {
    "type": "function", "name": "lookup", "description": "Look up a value",
    "parameters": {"type": "object", "properties": {"q": {"type": "string"}},
                   "required": ["q"], "additionalProperties": False},
}
ARGUMENTS = json.dumps({"q": "café"}, ensure_ascii=False)
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.fixture
def provider():
    state = SimpleNamespace(replies=deque(), requests=[], headers=[])

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state.requests.append((self.command, self.path, json.loads(body) if body else {}))
            state.headers.append(dict(self.headers))
            status, reply = state.replies.popleft() if state.replies else (500, {"error": "Unexpected request"})
            streaming = isinstance(reply, str)
            payload = (reply if streaming else json.dumps(reply)).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_DELETE = do_POST

        def log_message(self, *_args):
            pass

    clear_transport_capability_cache()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.kwargs = {"api_base": f"http://127.0.0.1:{server.server_port}/v1",
                    "api_key": "test-key", "num_retries": 0, "timeout": 5, "drop_params": True}
    try:
        yield state
        assert not state.replies, "An expected provider request was never sent"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        clear_transport_capability_cache()


def sse(events, *, done=False):
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events) + (
        "data: [DONE]\n\n" if done else ""
    )


def chat_reply(stream):
    base = {"id": "chatcmpl-test", "created": 1, "model": "gpt-4o"}
    call = {"index": 0, "id": "call_test", "type": "function",
            "function": {"name": "lookup", "arguments": ARGUMENTS}}
    if not stream:
        return {**base, "object": "chat.completion", "usage": USAGE,
                "choices": [{"index": 0, "finish_reason": "tool_calls",
                             "message": {"role": "assistant", "content": "Working.", "tool_calls": [call]}}]}
    return sse([
        {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "finish_reason": None,
          "delta": {"role": "assistant", "tool_calls": [{**call, "function": {"name": "lookup", "arguments": ""}}]}}]},
        {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "finish_reason": None,
          "delta": {"tool_calls": [{"index": 0, "function": {"arguments": ARGUMENTS}}]}}]},
        {**base, "object": "chat.completion.chunk", "choices": [{"index": 0, "finish_reason": "tool_calls", "delta": {}}]},
        {**base, "object": "chat.completion.chunk", "choices": [], "usage": USAGE},
    ], done=True)


def response_reply(stream):
    reasoning = {"id": "rs_test", "type": "reasoning", "summary": [], "encrypted_content": "opaque-state"}
    call = {"id": "fc_test", "type": "function_call", "call_id": "call_test", "name": "lookup",
            "arguments": ARGUMENTS, "status": "completed"}
    response = {"id": "resp_test", "object": "response", "created_at": 1, "model": "gpt-4o",
                "status": "completed", "output": [reasoning, call], "error": None, "incomplete_details": None,
                "parallel_tool_calls": False, "tools": [TOOL], "tool_choice": "required",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 2}}}
    if not stream:
        return response
    return sse([
        {"type": "response.created", "sequence_number": 0, "response": {**response, "status": "in_progress", "output": []}},
        {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": reasoning},
        {"type": "response.output_item.added", "sequence_number": 2, "output_index": 1,
         "item": {**call, "arguments": "", "status": "in_progress"}},
        {"type": "response.function_call_arguments.delta", "sequence_number": 3, "output_index": 1,
         "item_id": "fc_test", "delta": ARGUMENTS},
        {"type": "response.output_item.done", "sequence_number": 4, "output_index": 1, "item": call},
        {"type": "response.completed", "sequence_number": 5, "response": response},
    ])


@pytest.mark.asyncio
@pytest.mark.parametrize("async_call", [False, True])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("mode", ["chat_completions", "responses"])
async def test_sdk_tools_usage_and_state_over_http(provider, mode, stream, async_call):
    native = mode == "responses"
    provider.replies.append((200, response_reply(stream) if native else chat_reply(stream)))
    transport = LiteLLMTransport(
        model="openai/gpt-4o", messages=[{"role": "user", "content": "Look up café"}],
        kwargs={**provider.kwargs, "a0_api_mode": mode,
                **({"a0_responses_function_tools": [TOOL]} if native else {})},
    )
    if stream:
        chunks = [chunk async for chunk in transport.astream()] if async_call else list(transport.stream())
        assert "lookup" in "".join(chunk["response_delta"] for chunk in chunks)
    elif async_call:
        await transport.acomplete()
    else:
        transport.complete()
    result = transport.last_result
    assert result is not None and result.mode == mode
    assert result.function_calls[0].name == "lookup"
    assert result.function_calls[0].arguments == {"q": "café"}
    assert result.function_calls[0].call_id == "call_test"
    assert result.usage["total_tokens"] == 15
    method, path, body = provider.requests[0]
    assert method == "POST" and path == ("/v1/responses" if native else "/v1/chat/completions")
    assert not any(key.startswith("a0_") or key.startswith("responses_") for key in body)
    if native:
        assert result.output_items[0].data["encrypted_content"] == "opaque-state"
        assert body["tools"][0]["name"] == "lookup"
        assert body["tool_choice"] == "required" and body["parallel_tool_calls"] is False
        provider.replies.append((200, response_reply(False)))
        replay = LiteLLMTransport(
            model="openai/gpt-4o", messages=[], kwargs={**provider.kwargs, "a0_api_mode": "responses",
                "previous_response_id": result.response_id,
                "responses_input_items": [{"type": "function_call_output", "call_id": "call_test", "output": "Found"}]},
        )
        await replay.acomplete()
        assert provider.requests[1][2]["previous_response_id"] == "resp_test"
        assert provider.requests[1][2]["input"][0]["call_id"] == "call_test"
        provider.replies.append((200, {"id": "resp_test", "object": "response.deleted", "deleted": True}))
        assert delete_stored_response_ids([result.response_id], **provider.kwargs) == []
        assert provider.requests[2][:2] == ("DELETE", "/v1/responses/resp_test")
    elif stream:
        assert body["stream_options"]["include_usage"] is True


@pytest.mark.asyncio
async def test_sdk_responses_fallback_over_http(provider):
    provider.replies.extend([
        (404, {"error": {"message": "Responses endpoint not found", "type": "invalid_request_error"}}),
        (200, chat_reply(False)),
    ])
    transport = LiteLLMTransport(model="openai/gpt-4o", messages=[{"role": "user", "content": "Hello"}],
                                kwargs={**provider.kwargs, "a0_api_mode": "responses"})
    await transport.acomplete()
    assert [row[1] for row in provider.requests] == ["/v1/responses", "/v1/chat/completions"]
    assert transport.last_result.mode == "chat_completions"


def test_sdk_embedding_batch_over_http(provider):
    provider.replies.append((200, {"object": "list", "model": "text-embedding-3-small",
        "data": [{"object": "embedding", "index": i, "embedding": vector}
                 for i, vector in enumerate([[1.0, 0.0], [0.0, 1.0]])],
        "usage": {"prompt_tokens": 2, "total_tokens": 2}}))
    wrapper = models.LiteLLMEmbeddingWrapper("text-embedding-3-small", "openai", **provider.kwargs,
                                           a0_api_mode="responses")
    assert wrapper.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert provider.requests[0][1] == "/v1/embeddings"
    assert provider.requests[0][2]["input"] == ["first", "second"]
    assert "a0_api_mode" not in provider.requests[0][2]


def test_sdk_anthropic_cache_markers_over_http(provider):
    provider.replies.append((200, {"id": "msg_test", "type": "message", "role": "assistant",
        "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "Hello"}],
        "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}))
    transport = LiteLLMTransport(model="anthropic/claude-sonnet-4-5", messages=[
        {"role": "system", "content": "Stable instructions"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": [{"type": "text", "text": "Prior answer"}]},
        {"role": "user", "content": "Continue"},
    ], kwargs={**provider.kwargs, "api_base": provider.kwargs["api_base"].removesuffix("/v1"),
               "a0_explicit_prompt_caching": True, "max_tokens": 32})
    assert transport.complete()["response_delta"] == "Hello"
    assert provider.requests[0][1] == "/v1/messages"
    body = provider.requests[0][2]
    assert body["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][1]["content"][-1]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
@pytest.mark.parametrize("async_call", [False, True])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("provider_id,mode,expected", [
    ("venice", None, "prompt_cache_key"),
    ("a0_venice", None, "prompt_cache_key"),
    ("other", "prompt_cache_key", "prompt_cache_key"),
    ("other", "cache_control", "cache_control"),
    ("other", "auto", "off"),
    ("venice", "off", "off"),
])
async def test_sdk_provider_cache_routing_over_http(provider, monkeypatch, provider_id, mode, expected, stream, async_call):
    from copy import deepcopy
    from pathlib import Path
    import yaml
    from helpers.litellm_transport import _has_cache_control

    definitions = yaml.safe_load((Path(__file__).resolve().parents[1] / "conf/model_providers.yaml").read_text())
    monkeypatch.setattr(models, "get_provider_config", lambda kind, pid: definitions[kind].get(pid))
    monkeypatch.setattr(models, "get_api_key", lambda _pid: "test-key")
    wrapper = models.get_chat_model(provider_id, "llama-3.3-70b", **(
        {"a0_prompt_cache_mode": mode} if mode is not None else {}
    ))
    messages = [{"role": "system", "content": "Stable instructions"},
                {"role": "user", "content": "Hello"}]
    kwargs = {**wrapper.kwargs, **provider.kwargs, "a0_explicit_prompt_caching": True,
              "tools": [{"type": "function", "function": {k: v for k, v in TOOL.items() if k != "type"}}]}
    original = deepcopy((messages, kwargs))
    provider.replies.append((200, chat_reply(stream)))
    transport = LiteLLMTransport(model=wrapper.model_name, messages=messages, kwargs=kwargs)
    if stream:
        chunks = [chunk async for chunk in transport.astream()] if async_call else list(transport.stream())
        assert chunks
    elif async_call:
        await transport.acomplete()
    else:
        transport.complete()

    _, path, body = provider.requests[0]
    assert path == "/v1/chat/completions"
    assert (messages, kwargs) == original
    assert not any(key.startswith("a0_") for key in body)
    assert ("prompt_cache_key" in body) == (expected == "prompt_cache_key")
    assert _has_cache_control(body) == (expected == "cache_control")
    if expected == "prompt_cache_key":
        assert body["prompt_cache_key"].startswith("a0-")
    elif expected == "cache_control":
        assert body["messages"][0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert body["tools"][0]["function"]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["prompt_cache_key", "off"])
async def test_sdk_custom_responses_cache_mode_over_http(provider, mode):
    provider.replies.append((200, response_reply(False)))
    transport = LiteLLMTransport(
        model="openai/gpt-4o", messages=[{"role": "system", "content": "Stable instructions"}],
        kwargs={**provider.kwargs, "a0_api_mode": "responses", "a0_prompt_cache_mode": mode},
    )
    await transport.acomplete()
    _, path, body = provider.requests[0]
    assert path == "/v1/responses"
    assert ("prompt_cache_key" in body) == (mode == "prompt_cache_key")
    assert "a0_prompt_cache_mode" not in body


@pytest.mark.parametrize("provider_id,name,route,base", [
    ("cerebras", "gpt-oss-120b", "cerebras", "https://api.cerebras.ai/v1"),
    ("nebius", "meta-llama/Llama-3.3-70B-Instruct", "nebius", "https://api.tokenfactory.nebius.com/v1"),
    ("zai", "glm-4.6", "zai", "https://api.z.ai/api/paas/v4"),
    ("zai_coding", "glm-4.6", "zai", "https://api.z.ai/api/coding/paas/v4"),
    ("venice", "llama-3.3-70b", "veniceai", "https://api.venice.ai/api/v1"),
])
def test_native_provider_defaults_over_http(provider, monkeypatch, provider_id, name, route, base):
    from pathlib import Path
    import yaml
    import litellm
    from plugins._model_config.api.model_search import ModelSearch
    from plugins._model_config.helpers import model_config

    definitions = yaml.safe_load((Path(__file__).resolve().parents[1] / "conf/model_providers.yaml").read_text())
    lookup = lambda kind, pid: definitions[kind].get(pid)
    monkeypatch.setattr(models, "get_provider_config", lookup)
    monkeypatch.setattr(models, "get_api_key", lambda pid: f"test-{pid}")
    mc = model_config.build_model_config({"provider": provider_id, "name": name}, models.ModelType.CHAT)
    wrapper = models.get_chat_model(provider_id, name, model_config=mc, **mc.build_kwargs())
    assert wrapper.model_name == f"{route}/{name}"
    assert wrapper.kwargs["api_key"] == f"test-{provider_id}"
    assert litellm.get_llm_provider(model=wrapper.model_name, api_key=wrapper.kwargs["api_key"],
                                   api_base=wrapper.kwargs.get("api_base"))[3] == base
    cfg = definitions["chat"][provider_id]
    assert ModelSearch._resolve_url(cfg["models_list"], wrapper.kwargs.get("api_base", ""))[0] == f"{base}/models"

    provider.replies.append((200, chat_reply(False)))
    transport = LiteLLMTransport(model=wrapper.model_name, messages=[{"role": "user", "content": "Hello"}],
                                 kwargs={**wrapper.kwargs, **provider.kwargs})
    transport.complete()
    _, path, body = provider.requests[0]
    assert path == "/v1/chat/completions" and body["model"] == name
    if provider_id == "venice":
        assert body["venice_parameters"] == {"include_venice_system_prompt": False}


@pytest.mark.parametrize("kwargs,expected", [
    ({"extra_body": {"custom": 1}}, False),
    ({"venice_parameters": {"include_venice_system_prompt": True}, "extra_body": {"custom": 1}}, True),
    ({"venice_parameters": {"include_venice_system_prompt": False},
      "extra_body": {"custom": 1, "venice_parameters": {"include_venice_system_prompt": True}}}, True),
])
def test_saved_venice_parameters_over_http(provider, monkeypatch, kwargs, expected):
    from copy import deepcopy
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(models, "get_api_key", lambda pid: "test-key")
    original = deepcopy(kwargs)
    cfg = {"provider": "venice", "name": "llama-3.3-70b", "kwargs": kwargs}
    mc = model_config.build_model_config(cfg, models.ModelType.CHAT)
    wrapper = models.get_chat_model(mc.provider, mc.name, **mc.build_kwargs())
    provider.replies.append((200, chat_reply(False)))
    LiteLLMTransport(model=wrapper.model_name, messages=[{"role": "user", "content": "Hello"}],
                     kwargs={**wrapper.kwargs, **provider.kwargs}).complete()
    body = provider.requests[0][2]
    assert body["venice_parameters"] == {"include_venice_system_prompt": expected}
    assert body["custom"] == 1
    assert kwargs == original
    for pid, kind in [("a0_venice", models.ModelType.CHAT), ("venice", models.ModelType.EMBEDDING)]:
        assert model_config.build_model_config({**cfg, "provider": pid}, kind).kwargs == original


@pytest.mark.parametrize("name", ["google/gemini-embedding-001", "openai/text-embedding-3-small",
                                  "nvidia/llama-nemotron-embed-vl-1b-v2:free"])
def test_native_openrouter_embeddings_over_http(provider, monkeypatch, name):
    monkeypatch.setattr(models, "get_api_key", lambda pid: f"test-{pid}")
    wrapper = models.get_embedding_model("openrouter", name, **provider.kwargs)
    assert wrapper.model_name == f"openrouter/{name}"
    provider.replies.append((200, {"object": "list", "model": name,
        "data": [{"object": "embedding", "index": 0, "embedding": [1.0, 0.0]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1}}))
    assert wrapper.embed(["hello"]) == [[1.0, 0.0]]
    assert provider.requests[0][1] == "/v1/embeddings"
    assert provider.requests[0][2]["model"] == name
    headers = {key.lower(): value for key, value in provider.headers[0].items()}
    assert headers["http-referer"] == "https://agent-zero.ai/"
    assert headers["x-title"] == "Agent Zero"
    assert headers["x-openrouter-categories"] == "personal-agent,cloud-agent"


def test_native_copilot_supplies_headers_and_detects_vision(monkeypatch):
    from litellm.llms.github_copilot.chat.transformation import GithubCopilotConfig
    from litellm.llms.github_copilot.authenticator import Authenticator

    monkeypatch.setattr(Authenticator, "get_api_key", lambda self: "test-key")
    config = GithubCopilotConfig()
    for content, vision in [("Hello", False), ([{"type": "image_url", "image_url": {"url": "https://example.invalid/image.png"}}], True)]:
        headers = config.validate_environment(headers={}, model="gpt-4o",
            messages=[{"role": "user", "content": content}], optional_params={}, litellm_params={}, api_key="test-key")
        headers = {key.lower(): value for key, value in headers.items()}
        assert headers["copilot-integration-id"] == "vscode-chat"
        assert headers["editor-version"].startswith("vscode/")
        assert (headers.get("copilot-vision-request") == "true") == vision


def test_extra_body_defaults_merge_without_provider_specific_rules(monkeypatch):
    defaults = {"litellm_provider": "openai", "kwargs": {
        "extra_body": {"vendor_options": {"enabled": False}, "default_only": 1}}}
    monkeypatch.setattr(models, "get_provider_config", lambda kind, pid: defaults)
    monkeypatch.setattr(models, "get_api_key", lambda pid: "None")
    route, kwargs = models._merge_provider_defaults("chat", "test-provider", {
        "vendor_options": {"enabled": True}, "temperature": 0.2,
        "extra_body": {"vendor_options": {"enabled": False}, "custom": 2}})
    assert route == "openai"
    assert kwargs == {"temperature": 0.2, "extra_body": {
        "vendor_options": {"enabled": False}, "default_only": 1, "custom": 2}}
    assert defaults["kwargs"]["extra_body"] == {"vendor_options": {"enabled": False}, "default_only": 1}
    _, legacy = models._merge_provider_defaults("chat", "test-provider", {"vendor_options": {"enabled": True}})
    assert legacy["extra_body"]["vendor_options"] == {"enabled": True}
