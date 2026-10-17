"""Regression tests for post-turn chat persistence.

Root cause (2026-08-02): the regular chat save hook lives at
``extensions/python/message_loop_end/_90_save_chat.py``, which runs before
monologue_end extensions. Anything logged from monologue_end — the
"Waiting for input" progress reset and the memory plugin's memorize utility
items (created at loop end, filled in by a background task) — therefore
missed the turn's final save. The entries reached ``chat.json`` only when the
next turn triggered a save, and were lost entirely if the server restarted in
between (measured live: turn-2 memorize items of a finished chat were absent
from chat.json minutes after completion; turn-1's only appeared after the
user's next message).

Fix: a new ``extensions/python/monologue_end/_95_save_chat.py`` persists the
chat when the monologue ends (capturing the memorize items' creation and the
"Waiting for input" progress), and the memorize background tasks persist
their terminal state (final headings + finished marker) when they complete,
on every exit path.

These tests fail on the pre-fix sources (no monologue_end save extension, no
save call in the memorize tasks) and pass with the fix.
"""

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_extension_module(name: str):
    return importlib.import_module(
        f"plugins._memory.extensions.python.monologue_end.{name}"
    )


class FakeLogItem:
    def __init__(self):
        self.updates: list[dict] = []

    def update(self, **kwargs):
        self.updates.append(kwargs)

    def stream(self, **kwargs):
        pass


class FakeLog:
    def log(self, **kwargs):
        return FakeLogItem()


def _make_agent(context, utility_response=None, utility_error=None):
    async def call_utility_model(**kwargs):
        if utility_error is not None:
            raise utility_error
        return utility_response

    return SimpleNamespace(
        history=[],
        context=context,
        read_prompt=lambda *a, **k: "system prompt",
        concat_messages=lambda history: "chat text",
        call_utility_model=call_utility_model,
    )


def _patch_common(monkeypatch, mod):
    import helpers.plugins as plugins_mod

    monkeypatch.setattr(
        plugins_mod,
        "get_plugin_config",
        lambda plugin, agent=None, **kwargs: {
            "memory_memorize_enabled": True,
            "memory_memorize_consolidation": False,
            "memory_memorize_replace_threshold": 0,
        },
    )

    class FakeDB:
        async def delete_documents_by_query(self, **kwargs):
            return []

        async def insert_text(self, text, metadata=None):
            return "id"

    async def fake_get(agent):
        return FakeDB()

    monkeypatch.setattr(mod.Memory, "get", staticmethod(fake_get))


def _record_saves(monkeypatch):
    import helpers.persist_chat as persist_chat_mod

    saves: list = []
    monkeypatch.setattr(persist_chat_mod, "save_tmp_chat", saves.append)
    return saves


@pytest.mark.parametrize(
    "module_name",
    ["_50_memorize_fragments", "_51_memorize_solutions"],
)
def test_memorize_task_persists_chat_on_empty_result(monkeypatch, module_name):
    """The background memorize task must save the chat when it completes so
    its terminal log state does not wait for the next turn's save hook."""
    mod = _load_extension_module(module_name)
    _patch_common(monkeypatch, mod)
    saves = _record_saves(monkeypatch)

    context = SimpleNamespace(log=FakeLog(), id="ctx-test")
    cls = mod.MemorizeMemories if module_name.startswith("_50") else mod.MemorizeSolutions
    ext = cls(agent=None)
    ext.agent = _make_agent(context, utility_response="[]")

    asyncio.run(ext.memorize(loop_data=None, log_item=FakeLogItem()))

    assert saves == [context], (
        "memorize() completed without persisting the chat; its log entries "
        "would only reach chat.json on the next turn"
    )


@pytest.mark.parametrize(
    "module_name",
    ["_50_memorize_fragments", "_51_memorize_solutions"],
)
def test_memorize_task_persists_chat_on_utility_error(monkeypatch, module_name):
    """The persistence must also fire on the failure exit path."""
    mod = _load_extension_module(module_name)
    _patch_common(monkeypatch, mod)
    saves = _record_saves(monkeypatch)

    context = SimpleNamespace(log=FakeLog(), id="ctx-test")
    cls = mod.MemorizeMemories if module_name.startswith("_50") else mod.MemorizeSolutions
    ext = cls(agent=None)
    ext.agent = _make_agent(context, utility_error=RuntimeError("provider exploded"))

    asyncio.run(ext.memorize(loop_data=None, log_item=FakeLogItem()))

    assert saves == [context]


def test_monologue_end_save_extension_persists_regular_context(monkeypatch):
    """The monologue_end save hook captures post-message-loop log state
    (memorize item creation, "Waiting for input" progress) at turn end."""
    from agent import AgentContextType
    from extensions.python.monologue_end._95_save_chat import SaveChat

    saves = _record_saves(monkeypatch)
    context = SimpleNamespace(type=AgentContextType.USER, id="ctx-user")
    ext = SaveChat(agent=SimpleNamespace(context=context))

    asyncio.run(ext.execute(loop_data=None))

    assert saves == [context]


def test_monologue_end_save_extension_skips_background_context(monkeypatch):
    """BACKGROUND contexts are ephemeral and must not be persisted."""
    from agent import AgentContextType
    from extensions.python.monologue_end._95_save_chat import SaveChat

    saves = _record_saves(monkeypatch)
    context = SimpleNamespace(type=AgentContextType.BACKGROUND, id="ctx-bg")
    ext = SaveChat(agent=SimpleNamespace(context=context))

    asyncio.run(ext.execute(loop_data=None))

    assert saves == []
