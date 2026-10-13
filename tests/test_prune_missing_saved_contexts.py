"""Regression for agent0ai/agent-zero#1947.

A stale saved_chat_ids() listing taken before a concurrent first save must not
remove the newly saved context. Confirm on disk before removing.

Heavy Agent Zero runtime deps are stubbed so this file stays runnable in a
minimal pytest + pytz environment.
"""

from __future__ import annotations

import enum
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("pytz")


def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    if "." in name:
        parent_name, attr = name.rsplit(".", 1)
        parent = _ensure_module(parent_name)
        setattr(parent, attr, mod)
    return mod


def _install_stubs() -> types.ModuleType:
    """Install lightweight stubs when the real agent stack is unavailable."""
    try:
        import agent as real_agent  # noqa: F401

        return sys.modules["agent"]
    except Exception:
        pass

    agent_mod = _ensure_module("agent")

    class AgentContextType(enum.Enum):
        USER = "user"
        TASK = "task"
        BACKGROUND = "background"

    class AgentContext:
        _contexts: dict = {}

        @classmethod
        def all(cls):
            return list(cls._contexts.values())

        @classmethod
        def remove(cls, ctxid: str):
            cls._contexts.pop(ctxid, None)

        @classmethod
        def reset_for_tests(cls):
            cls._contexts.clear()

    agent_mod.AgentContext = AgentContext
    agent_mod.AgentContextType = AgentContextType
    agent_mod.Agent = object
    agent_mod.AgentConfig = object

    # state_snapshot top-level helper imports
    dotenv = _ensure_module("helpers.dotenv")
    dotenv.get_dotenv_value = lambda *a, **k: None

    localization = _ensure_module("helpers.localization")

    class Localization:
        @staticmethod
        def get():
            return Localization()

        def get_timezone(self):
            return "UTC"

        def set_timezone(self, tz):
            return None

    localization.Localization = Localization

    task_scheduler = _ensure_module("helpers.task_scheduler")

    class TaskScheduler:
        @staticmethod
        def get():
            return TaskScheduler()

        def get_task_by_uuid(self, _id):
            return None

        def serialize_task(self, _id):
            return None

    task_scheduler.TaskScheduler = TaskScheduler

    # persist_chat stand-in for the inner import in _prune_missing_saved_contexts
    persist_chat = _ensure_module("helpers.persist_chat")
    if not hasattr(persist_chat, "SAVED_CHAT_CONTEXT_DATA_KEY"):
        persist_chat.SAVED_CHAT_CONTEXT_DATA_KEY = "_persist_chat_saved"
    if not hasattr(persist_chat, "saved_chat_ids"):
        persist_chat.saved_chat_ids = lambda: set()
    if not hasattr(persist_chat, "chat_file_exists"):
        persist_chat.chat_file_exists = lambda ctxid: False

    return agent_mod


@pytest.fixture
def prune_env(monkeypatch):
    agent_mod = _install_stubs()

    # Fresh load of state_snapshot against stubs
    sys.modules.pop("helpers.state_snapshot", None)
    state_snapshot = importlib.import_module("helpers.state_snapshot")
    persist_chat = sys.modules["helpers.persist_chat"]

    if hasattr(agent_mod.AgentContext, "reset_for_tests"):
        agent_mod.AgentContext.reset_for_tests()

    yield state_snapshot, persist_chat, agent_mod

    if hasattr(agent_mod.AgentContext, "reset_for_tests"):
        agent_mod.AgentContext.reset_for_tests()


def test_prune_keeps_context_when_stale_listing_misses_existing_file(prune_env, monkeypatch):
    state_snapshot, persist_chat, agent_mod = prune_env
    AgentContext = agent_mod.AgentContext
    AgentContextType = agent_mod.AgentContextType

    removed: list[str] = []
    ctx = SimpleNamespace(
        id="just-saved",
        type=AgentContextType.USER,
        data={persist_chat.SAVED_CHAT_CONTEXT_DATA_KEY: True},
        is_running=lambda: False,
    )

    monkeypatch.setattr(AgentContext, "all", classmethod(lambda cls: [ctx]))
    monkeypatch.setattr(
        AgentContext, "remove", classmethod(lambda cls, ctxid: removed.append(ctxid))
    )
    monkeypatch.setattr(persist_chat, "saved_chat_ids", lambda: set())
    monkeypatch.setattr(persist_chat, "chat_file_exists", lambda ctxid: ctxid == "just-saved")

    state_snapshot._prune_missing_saved_contexts()
    assert removed == []


def test_prune_removes_context_when_file_truly_gone(prune_env, monkeypatch):
    state_snapshot, persist_chat, agent_mod = prune_env
    AgentContext = agent_mod.AgentContext
    AgentContextType = agent_mod.AgentContextType

    removed: list[str] = []
    ctx = SimpleNamespace(
        id="deleted-chat",
        type=AgentContextType.USER,
        data={persist_chat.SAVED_CHAT_CONTEXT_DATA_KEY: True},
        is_running=lambda: False,
    )

    monkeypatch.setattr(AgentContext, "all", classmethod(lambda cls: [ctx]))
    monkeypatch.setattr(
        AgentContext, "remove", classmethod(lambda cls, ctxid: removed.append(ctxid))
    )
    monkeypatch.setattr(persist_chat, "saved_chat_ids", lambda: set())
    monkeypatch.setattr(persist_chat, "chat_file_exists", lambda ctxid: False)

    state_snapshot._prune_missing_saved_contexts()
    assert removed == ["deleted-chat"]


def test_source_contract_chat_file_exists_recheck():
    persist = (PROJECT_ROOT / "helpers" / "persist_chat.py").read_text(encoding="utf-8")
    snapshot = (PROJECT_ROOT / "helpers" / "state_snapshot.py").read_text(encoding="utf-8")
    assert "def chat_file_exists(ctxid: str)" in persist
    assert "persist_chat.chat_file_exists(ctx.id)" in snapshot
