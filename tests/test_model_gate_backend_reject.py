import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins._model_config.extensions.python.user_message_ui._10_check_chat_model import (
    CheckChatModel,
)

_PATCH_TARGET = "plugins._model_config.helpers.model_config.get_effective_config"


class _StubConfig:
    profile = "none"


class _StubContext:
    def get_data(self, _key):
        return None


class _StubAgent:
    config = _StubConfig()
    context = _StubContext()


def test_check_chat_model_flags_unconfigured(monkeypatch):
    monkeypatch.setattr(_PATCH_TARGET, lambda agent: {})
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.is_chat_model_configured",
        lambda config: False,
    )
    data = {"message": "hello", "attachment_paths": []}
    asyncio.run(CheckChatModel(agent=_StubAgent()).execute(data=data))
    assert data["model_not_configured"] is True


def test_check_chat_model_passes_configured(monkeypatch):
    monkeypatch.setattr(_PATCH_TARGET, lambda agent: {})
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.is_chat_model_configured",
        lambda config: True,
    )
    data = {"message": "hello", "attachment_paths": []}
    asyncio.run(CheckChatModel(agent=_StubAgent()).execute(data=data))
    assert "model_not_configured" not in data


def test_check_chat_model_skips_missing_agent():
    data = {"message": "hello", "attachment_paths": []}
    asyncio.run(CheckChatModel(agent=None).execute(data=data))
    assert "model_not_configured" not in data


def test_message_communicate_rejects_unconfigured(monkeypatch):
    from api.message import Message

    handler = Message.__new__(Message)
    context = type("Ctx", (), {})()
    context.get_agent = lambda: _StubAgent()

    def _no_dispatch(msg):
        raise AssertionError("must not dispatch")

    context.communicate = _no_dispatch
    handler.use_context = lambda ctxid: context

    request = type("Req", (), {})()
    request.content_type = "application/json"
    request.get_json = lambda: {"text": "hello", "context": ""}

    async def fake_call(point, agent=None, **kwargs):
        data = kwargs["data"]
        data["model_not_configured"] = True

    monkeypatch.setattr("api.message.extension.call_extensions_async", fake_call)

    task, ctx = asyncio.run(handler.communicate(input={}, request=request))
    assert task is None
    assert ctx is context
