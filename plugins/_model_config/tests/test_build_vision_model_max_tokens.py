from plugins._model_config.helpers import model_config


class _StubChatModel:
    def __init__(self, provider, name, model_config=None, **kwargs):
        self.provider = provider
        self.name = name
        self.model_config = model_config
        self.kwargs = kwargs


def _patch_builder(monkeypatch, cfg):
    """Stub config resolution and model construction; return kwargs capture."""
    monkeypatch.setattr(
        model_config, "get_vision_model_config", lambda agent=None: dict(cfg)
    )
    captured = {}

    def fake_get_chat_model(provider, name, model_config=None, **kwargs):
        captured["provider"] = provider
        captured["name"] = name
        captured["kwargs"] = kwargs
        return _StubChatModel(provider, name, model_config=model_config, **kwargs)

    monkeypatch.setattr(model_config.models, "get_chat_model", fake_get_chat_model)
    return captured


def _base_cfg(**extra):
    cfg = {
        "provider": "openai",
        "name": "gpt-4o-mini",
        "api_key": "",
        "kwargs": {},
    }
    cfg.update(extra)
    return cfg


def test_max_tokens_injected_without_max_completion_tokens(monkeypatch):
    """No kwargs collision: default max_tokens is still injected."""
    captured = _patch_builder(monkeypatch, _base_cfg())
    model_config.build_vision_model()
    kwargs = captured["kwargs"]
    assert kwargs["max_tokens"] == model_config.DEFAULT_VISION_MAX_TOKENS
    assert kwargs["timeout"] == model_config.DEFAULT_VISION_TIMEOUT_SECONDS
    assert "max_completion_tokens" not in kwargs


def test_max_tokens_not_injected_with_max_completion_tokens(monkeypatch):
    """Regression: preset kwargs with max_completion_tokens must not get
    max_tokens injected too; OpenAI rejects requests setting both."""
    captured = _patch_builder(
        monkeypatch,
        _base_cfg(kwargs={"max_completion_tokens": 32768}),
    )
    model_config.build_vision_model()
    kwargs = captured["kwargs"]
    assert "max_tokens" not in kwargs
    assert kwargs["max_completion_tokens"] == 32768
    assert kwargs["timeout"] == model_config.DEFAULT_VISION_TIMEOUT_SECONDS


def test_explicit_slot_max_tokens_injected_without_collision(monkeypatch):
    """Explicit slot-level max_tokens with no kwargs collision is injected."""
    captured = _patch_builder(monkeypatch, _base_cfg(max_tokens=4096))
    model_config.build_vision_model()
    kwargs = captured["kwargs"]
    assert kwargs["max_tokens"] == 4096
    assert kwargs["timeout"] == model_config.DEFAULT_VISION_TIMEOUT_SECONDS
    assert "max_completion_tokens" not in kwargs


def test_max_completion_tokens_wins_over_slot_max_tokens(monkeypatch):
    """Both set: max_completion_tokens wins, max_tokens is never injected.
    Mirrors the Responses-API de-collision precedence in
    helpers/litellm_transport.py (max_completion_tokens or max_tokens)."""
    captured = _patch_builder(
        monkeypatch,
        _base_cfg(max_tokens=4096, kwargs={"max_completion_tokens": 32768}),
    )
    model_config.build_vision_model()
    kwargs = captured["kwargs"]
    assert "max_tokens" not in kwargs
    assert kwargs["max_completion_tokens"] == 32768
