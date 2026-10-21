from types import SimpleNamespace

import models
from plugins._model_config.api.model_search import ModelSearch
from plugins._model_config.helpers import model_config
from plugins._model_config.helpers.opencode_go import (
    apply_opencode_go_route,
    classify_opencode_go_model,
)


def test_opencode_go_classifies_documented_and_prefixed_models():
    assert classify_opencode_go_model("glm-5.3-flash") == "chat"
    assert classify_opencode_go_model("glm-5.1") == "chat"
    assert classify_opencode_go_model("step-5-preview") == "chat"
    assert classify_opencode_go_model("grok-4.7") == "responses"
    assert classify_opencode_go_model("gpt-6-luna") == "responses"
    assert classify_opencode_go_model("qwen3.8-max") == "messages"
    assert classify_opencode_go_model("qwen3.7-max") == "messages"
    assert classify_opencode_go_model("minimax-m2.5") == "messages"
    assert classify_opencode_go_model("omen-alpha") == "chat"
    assert classify_opencode_go_model("beam-free") == "chat"


def test_opencode_go_route_respects_explicit_kwargs_and_context(monkeypatch):
    monkeypatch.setattr(
        "plugins._model_config.helpers.opencode_go.agent_zero_user_agent",
        lambda: "agent-zero/test",
    )
    agent = SimpleNamespace(context=SimpleNamespace(id="chat-9"))

    chat = apply_opencode_go_route("opencode", "glm-5.3-flash", {}, agent)
    assert "a0_api_mode" not in chat
    assert "a0_responses_fallback" not in chat
    assert "a0_litellm_provider" not in chat
    assert chat["extra_headers"]["User-Agent"] == "agent-zero/test"
    assert chat["extra_headers"]["x-opencode-session"] == "agent-zero-chat-9"

    responses = apply_opencode_go_route("opencode", "grok-4.7", {
        "a0_api_mode": "chat",
        "a0_responses_fallback": True,
        "extra_headers": {"User-Agent": "custom/1"},
    }, None)
    assert responses["a0_api_mode"] == "chat"
    assert responses["a0_responses_fallback"] is True
    assert responses["extra_headers"]["User-Agent"] == "custom/1"
    assert "x-opencode-session" not in responses["extra_headers"]

    messages = apply_opencode_go_route("opencode", "qwen3.8-max", {
        "api_base": "https://proxy.example/go",
    }, agent)
    assert messages["a0_litellm_provider"] == "anthropic"
    assert messages["api_base"] == "https://proxy.example/go"

    untouched = {"temperature": 0}
    assert apply_opencode_go_route("openai", "gpt-4o", untouched, agent) is untouched


def test_opencode_go_builders_share_the_route(monkeypatch):
    captured = []

    def fake_get_chat_model(provider, name, model_config=None, **kwargs):
        captured.append((provider, name, kwargs))
        return kwargs

    monkeypatch.setattr(model_config.models, "get_chat_model", fake_get_chat_model)
    monkeypatch.setattr(
        "plugins._model_config.helpers.opencode_go.agent_zero_user_agent",
        lambda: "agent-zero/test",
    )
    agent = SimpleNamespace(context=SimpleNamespace(id="chat-9"))
    cfg = {"provider": "opencode", "name": "muse-spark-1.2-contributor", "kwargs": {}}
    monkeypatch.setattr(model_config, "get_chat_model_config", lambda agent=None: cfg)
    monkeypatch.setattr(model_config, "get_utility_model_config", lambda agent=None: cfg)
    monkeypatch.setattr(model_config, "get_vision_model_config", lambda agent=None: cfg)

    model_config.build_chat_model(agent)
    model_config.build_utility_model(agent)
    model_config.build_vision_model(agent)

    assert len(captured) == 3
    for provider, name, kwargs in captured:
        assert provider == "opencode"
        assert name == "muse-spark-1.2-contributor"
        assert kwargs["a0_api_mode"] == "responses"
        assert kwargs["a0_responses_fallback"] is False
        assert kwargs["extra_headers"]["x-opencode-session"] == "agent-zero-chat-9"


def test_opencode_api_key_accepts_official_env_name(monkeypatch):
    def fake_dotenv(key, default=None):
        if key == "OPENCODE_API_KEY":
            return "go-key"
        return default

    monkeypatch.setattr(models.dotenv, "get_dotenv_value", fake_dotenv)
    assert models.get_api_key_raw("opencode") == "go-key"


def test_opencode_go_model_search_uses_live_catalog():
    from pathlib import Path
    import yaml

    definitions = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "conf/model_providers.yaml").read_text()
    )
    provider = definitions["chat"]["opencode"]
    url, fmt = ModelSearch._resolve_url(provider["models_list"], "")
    assert url == "https://opencode.ai/zen/go/v1/models"
    assert fmt == "openai"
    assert "embedding" not in definitions or "opencode" not in definitions["embedding"]
    handler = ModelSearch.__new__(ModelSearch)
    assert handler._parse({"object": "list", "data": [{"id": "glm-5.3-flash"}]}, fmt) == [
        "glm-5.3-flash"
    ]
