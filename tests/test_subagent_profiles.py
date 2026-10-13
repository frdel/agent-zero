from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import threading
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import Agent, AgentConfig, AgentContext
from helpers import persist_chat, projects, settings
from helpers.defer import DeferredTask
from helpers.errors import RepairableException


class _FakeContext:
    def __init__(self, id: str = "ctx") -> None:
        self.id = id
        self.name = None
        self.data = {}
        self.output_data = {}
        self.created_at = datetime.now(timezone.utc)
        self.agent0 = None
        self.task = None

    def get_data(self, key: str, recursive: bool = True):
        return self.data.get(key)

    def set_data(self, key: str, value, recursive: bool = True):
        self.data[key] = value

    def get_output_data(self, key: str, recursive: bool = True):
        return self.output_data.get(key)

    def set_output_data(self, key: str, value, recursive: bool = True):
        self.output_data[key] = value

    def is_running(self) -> bool:
        return bool(self.task and self.task.is_alive())

    def run_task(self, func, *args):
        self.task = DeferredTask().start_task(func, *args)
        return self.task


class _FakeParentAgent:
    def __init__(self) -> None:
        self.number = 0
        self.agent_name = "A0"
        self.config = AgentConfig(mcp_servers="", profile="agent0")
        self.context = _FakeContext()
        self.data = {}

    def get_data(self, key: str):
        return self.data.get(key)

    def set_data(self, key: str, value):
        self.data[key] = value

    def read_prompt(self, _file: str, **_kwargs) -> str:
        return ""


def test_hidden_default_profile_normalizes_to_agent0() -> None:
    configured = settings.get_default_settings()
    configured["agent_profile"] = "default"

    assert settings.normalize_settings(configured)["agent_profile"] == "agent0"


class _FakeSubAgent:
    DATA_NAME_SUPERIOR = "_superior"
    DATA_NAME_SUBORDINATE = "_subordinate"

    _counter = 0

    def __init__(self, number: int, config: AgentConfig, context=None) -> None:
        if context is None:
            self.__class__._counter += 1
            context = _FakeContext(f"child-{self.__class__._counter}")
        self.number = number
        self.agent_name = f"A{number}"
        self.config = config
        self.context = context
        self.context.agent0 = self
        self.data = {}
        self.history = SimpleNamespace(new_topic=lambda: None)
        self.messages = []

    def set_data(self, key: str, value):
        self.data[key] = value

    def get_data(self, key: str):
        return self.data.get(key)

    def hist_add_user_message(self, message):
        self.messages.append(message)

    async def monologue(self):
        return "delegated"


@pytest.mark.asyncio
async def test_call_subordinate_rejects_unknown_profile(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(
        call_subordinate,
        "_subordinate_profile_labels",
        lambda _agent: {"developer": "Developer", "researcher": "Researcher"},
    )
    parent = _FakeParentAgent()
    tool = call_subordinate.Delegation(
        parent,  # type: ignore[arg-type]
        "call_subordinate",
        None,
        {"profile": "ghost", "message": "work"},
        "",
        None,
    )

    with pytest.raises(RepairableException, match="Agent profile 'ghost' not found"):
        await tool.execute(message="work", profile="ghost", reset=True)

    assert parent.data == {}


@pytest.mark.asyncio
async def test_call_subordinate_uses_valid_profile(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(call_subordinate, "Agent", _FakeSubAgent)
    monkeypatch.setattr(
        call_subordinate,
        "_subordinate_profile_labels",
        lambda _agent: {"developer": "Developer"},
    )
    monkeypatch.setattr(
        call_subordinate,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", "agent0"),
        ),
    )
    monkeypatch.setattr(
        call_subordinate.message_queue, "log_user_message", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        call_subordinate.persist_chat, "save_tmp_chat", lambda _context: None
    )

    parent = _FakeParentAgent()
    tool = call_subordinate.Delegation(
        parent,  # type: ignore[arg-type]
        "call_subordinate",
        None,
        {"profile": "developer", "message": "work"},
        "",
        None,
    )

    response = await tool.execute(message="work", profile="developer", reset=True)
    children = parent.get_data(call_subordinate.SUBORDINATES_DATA_KEY)
    child = next(iter(children.values()))

    assert response.message == "delegated"
    assert response.additional == {"context_id": child.context.id}
    assert child.number == 1
    assert child.config.profile == "developer"
    assert child.messages[0].message == "work"


@pytest.mark.asyncio
async def test_call_subordinate_reset_false_reuses_numbered_child(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(call_subordinate, "Agent", _FakeSubAgent)
    monkeypatch.setattr(
        call_subordinate, "_subordinate_profile_labels", lambda _agent: {}
    )
    monkeypatch.setattr(
        call_subordinate,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(mcp_servers="", profile="agent0"),
    )
    monkeypatch.setattr(
        call_subordinate.message_queue, "log_user_message", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        call_subordinate.persist_chat, "save_tmp_chat", lambda _context: None
    )

    parent = _FakeParentAgent()
    tool = call_subordinate.Delegation(
        parent,  # type: ignore[arg-type]
        "call_subordinate",
        None,
        {},
        "",
        None,
    )
    first = await tool.execute(message="first", reset=True)
    second = await tool.execute(
        message="continue",
        context_id=first.additional["context_id"],  # type: ignore[index]
        reset=False,
    )

    children = parent.get_data(call_subordinate.SUBORDINATES_DATA_KEY)
    child = next(iter(children.values()))
    assert len(children) == 1
    assert child.number == 1
    assert [message.message for message in child.messages] == ["first", "continue"]
    assert second.additional == first.additional


@pytest.mark.parametrize(
    "project_name,project_preset,profile_project",
    [
        ("", None, ""),
        ("demo", None, ""),
        ("demo", "Default", ""),
        ("demo", "Project", ""),
        ("demo", "Project", "demo"),
    ],
    ids=["no-project", "project-inherits", "project-default", "project-preset", "project-profile"],
)
@pytest.mark.parametrize("preset", [None, "Default", "Cheap", "Missing"])
@pytest.mark.parametrize(
    "override",
    [None, {"preset_name": "Expensive"}, {"provider": "test", "name": "Expensive"}],
)
def test_subordinate_preserves_scoped_model_preset(
    monkeypatch, tmp_path, project_name, project_preset, profile_project, preset, override
) -> None:
    import tools.call_subordinate as call_subordinate
    from helpers import cache, files, plugins
    from plugins._model_config.helpers import model_config

    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    monkeypatch.setattr(cache, "_cache", {})
    monkeypatch.setattr(AgentContext, "_contexts", {})
    monkeypatch.setattr(persist_chat, "save_tmp_chat", lambda _context: None)
    monkeypatch.setattr(
        call_subordinate,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="", profile=override_settings["agent_profile"]
        ),
    )

    plugin_source = Path(__file__).resolve().parents[1] / "plugins" / "_model_config"
    for filename in ("plugin.yaml", "hooks.py", "default_config.yaml"):
        files.write_file(
            files.get_abs_path("plugins", "_model_config", filename),
            (plugin_source / filename).read_text(encoding="utf-8"),
        )
    files.write_file(
        files.get_abs_path("usr/plugins/_model_config/presets.yaml"),
        json.dumps([
            {
                "name": name,
                **{
                    slot: {"provider": "test", "name": name}
                    for slot in ("chat", "utility", "embedding")
                },
            }
            for name in ("Default", "Cheap", "Project", "Expensive")
        ]),
    )
    for profile in ("agent0", "developer"):
        files.write_file(files.get_abs_path("agents", profile, "agent.yaml"), "{}")
    if project_name:
        projects.create_project(project_name, {"title": "Demo"})
    for project, profile, selection in (
        (project_name, "", project_preset),
        (profile_project, "developer", preset),
    ):
        if selection is not None:
            files.write_file(
                plugins.determine_plugin_asset_path("_model_config", project, profile, "config.json"),
                json.dumps({"model_preset": selection}),
            )

    parent = Agent(0, AgentConfig(mcp_servers="", profile="agent0"))
    if project_name:
        projects.activate_project(parent.context.id, project_name, mark_dirty=False)
    parent.context.set_data("chat_model_override", override)
    child = call_subordinate.get_or_create_subordinate(
        parent, profile="developer", reset=True
    )

    configured = preset if profile_project and preset else project_preset or preset
    configured = configured if configured in {"Cheap", "Project"} else "Default"
    expected = "Expensive" if configured == "Default" and override else configured
    assert child.config.profile == "developer"
    assert projects.get_context_project_name(child.context) == (project_name or None)
    assert model_config.get_configured_preset_name(child) == configured
    assert model_config.get_chat_model_config(child)["name"] == expected
    assert child.context.get_data("chat_model_override") == (
        override if configured == "Default" else None
    )
    assert parent.context.get_data("chat_model_override") == override

    child.context.set_data("chat_model_override", {"preset_name": "Expensive"})
    resumed = call_subordinate.get_or_create_subordinate(parent, context_id=child.context.id)
    assert resumed is child
    assert model_config.get_chat_model_config(resumed)["name"] == "Expensive"


def test_subordinate_tree_numbers_each_generation(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(call_subordinate, "Agent", _FakeSubAgent)
    monkeypatch.setattr(
        call_subordinate, "_subordinate_profile_labels", lambda _agent: {}
    )
    monkeypatch.setattr(
        call_subordinate,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(mcp_servers="", profile="agent0"),
    )

    parent = _FakeParentAgent()
    child = call_subordinate.get_or_create_subordinate(
        parent,  # type: ignore[arg-type]
        reset=True,
        message="A1 work",
    )
    grandchild = call_subordinate.get_or_create_subordinate(
        child,  # type: ignore[arg-type]
        reset=True,
        message="A2 work",
    )

    assert child.number == 1
    assert grandchild.number == 2
    assert child.context.get_output_data("parent_context_id") == parent.context.id
    assert grandchild.context.get_output_data("parent_context_id") == child.context.id
    assert grandchild.get_data(Agent.DATA_NAME_SUPERIOR) is child


def test_subordinate_context_id_is_scoped_to_its_parent(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(call_subordinate, "Agent", _FakeSubAgent)
    monkeypatch.setattr(
        call_subordinate, "_subordinate_profile_labels", lambda _agent: {}
    )
    monkeypatch.setattr(
        call_subordinate,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(mcp_servers="", profile="agent0"),
    )

    owner = _FakeParentAgent()
    other = _FakeParentAgent()
    other.context = _FakeContext("other-parent")
    child = call_subordinate.get_or_create_subordinate(
        owner,  # type: ignore[arg-type]
        reset=True,
        message="private branch",
    )

    with pytest.raises(RepairableException, match="was not found under A0"):
        call_subordinate.get_or_create_subordinate(
            other,  # type: ignore[arg-type]
            context_id=child.context.id,
            reset=False,
        )


@pytest.mark.asyncio
async def test_call_subordinate_requires_reset_to_change_existing_profile(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    monkeypatch.setattr(
        call_subordinate,
        "_subordinate_profile_labels",
        lambda _agent: {"developer": "Developer", "researcher": "Researcher"},
    )

    parent = _FakeParentAgent()
    existing = SimpleNamespace(config=AgentConfig(mcp_servers="", profile="developer"))
    parent.set_data(_FakeSubAgent.DATA_NAME_SUBORDINATE, existing)
    tool = call_subordinate.Delegation(
        parent,  # type: ignore[arg-type]
        "call_subordinate",
        None,
        {"profile": "researcher", "message": "work"},
        "",
        None,
    )

    with pytest.raises(RepairableException, match="Set reset=true"):
        await tool.execute(message="work", profile="researcher", reset=False)


def test_persist_chat_roundtrip_preserves_each_agent_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        persist_chat,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", "agent0"),
        ),
    )

    context_id = "ctx-subagent-profile"
    AgentContext.remove(context_id)
    context = AgentContext(
        config=AgentConfig(mcp_servers="", profile="agent0"),
        id=context_id,
        set_current=False,
    )
    child = Agent(1, AgentConfig(mcp_servers="", profile="developer"), context)
    context.agent0.set_data(Agent.DATA_NAME_SUBORDINATE, child)
    child.set_data(Agent.DATA_NAME_SUPERIOR, context.agent0)

    try:
        serialized = persist_chat._serialize_context(context)
        assert serialized["agent_profile"] == "agent0"
        assert serialized["agents"][0]["agent_profile"] == "agent0"
        assert serialized["agents"][1]["agent_profile"] == "developer"

        AgentContext.remove(context_id)
        restored = persist_chat._deserialize_context(serialized)
        restored_child = restored.agent0.get_data(Agent.DATA_NAME_SUBORDINATE)

        assert restored.config.profile == "agent0"
        assert restored.agent0.config.profile == "agent0"
        assert restored_child.config.profile == "developer"
    finally:
        AgentContext.remove(context_id)


def test_persisted_numbered_child_is_reusable_after_reload(monkeypatch) -> None:
    import tools.call_subordinate as call_subordinate

    config_factory = lambda override_settings=None: AgentConfig(
        mcp_servers="",
        profile=(override_settings or {}).get("agent_profile", "agent0"),
    )
    monkeypatch.setattr(
        persist_chat,
        "initialize_agent",
        config_factory,
    )
    monkeypatch.setattr(call_subordinate, "initialize_agent", config_factory)

    parent_id = "ctx-persisted-agent-tree-parent"
    AgentContext.remove(parent_id)
    parent = AgentContext(
        AgentConfig(mcp_servers="", profile="agent0"),
        id=parent_id,
        set_current=False,
    )
    child = call_subordinate.get_or_create_subordinate(
        parent.agent0,
        reset=True,
        message="persist me",
        name="Original worker",
    )
    context_id = child.context.id
    try:
        assert len(persist_chat._serialize_context(parent)["agents"]) == 1
        serialized = persist_chat._serialize_context(child.context)
        AgentContext.remove(context_id)
        parent.agent0.data.pop(call_subordinate.SUBORDINATES_DATA_KEY, None)
        restored = persist_chat._deserialize_context(serialized)
        resumed = call_subordinate.get_or_create_subordinate(
            parent.agent0,
            context_id=context_id,
            reset=False,
        )

        assert restored.agent0.number == 1
        assert restored.agent0.agent_name == "A1"
        assert restored.get_output_data("parent_context_id") == parent.id
        assert restored.get_output_data("parent_agent_number") == 0
        assert resumed is restored.agent0
        assert resumed.get_data(Agent.DATA_NAME_SUPERIOR) is parent.agent0
        assert restored.name == restored.get_output_data("parent_context_label") == "Original worker"
        call_subordinate.get_or_create_subordinate(parent.agent0, context_id=context_id, name="Renamed worker")
        renamed = persist_chat._serialize_context(restored)
        AgentContext.remove(context_id)
        restored = persist_chat._deserialize_context(renamed)
        assert restored.name == restored.get_output_data("parent_context_label") == "Renamed worker"
    finally:
        AgentContext.remove(context_id)
        AgentContext.remove(parent_id)


@pytest.mark.parametrize("project_name", [None, "demo"], ids=["global", "project"])
@pytest.mark.asyncio
async def test_agent_profile_set_uses_scope_and_preserves_subagent_profile(
    monkeypatch, project_name
) -> None:
    import api.agent_profile_set as agent_profile_set

    requested_scopes = []
    monkeypatch.setattr(
        agent_profile_set.subagents,
        "get_agents_dict",
        lambda scope: requested_scopes.append(scope)
        or {"researcher": SimpleNamespace(title="Researcher", enabled=True)},
    )
    monkeypatch.setattr(
        agent_profile_set,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", "agent0"),
        ),
    )
    monkeypatch.setattr(agent_profile_set, "save_tmp_chat", lambda _context: None)
    monkeypatch.setattr(
        agent_profile_set,
        "mark_dirty_for_context",
        lambda *_args, **_kwargs: None,
    )

    context_id = "ctx-profile-switch"
    AgentContext.remove(context_id)
    context = AgentContext(
        config=AgentConfig(mcp_servers="", profile="agent0"),
        id=context_id,
        set_current=False,
    )
    child = Agent(1, AgentConfig(mcp_servers="", profile="developer"), context)
    context.agent0.set_data(Agent.DATA_NAME_SUBORDINATE, child)
    child.set_data(Agent.DATA_NAME_SUPERIOR, context.agent0)
    if project_name:
        context.set_data(projects.CONTEXT_DATA_KEY_PROJECT, project_name)

    try:
        handler = agent_profile_set.SetAgentProfile.__new__(
            agent_profile_set.SetAgentProfile
        )
        response = await handler.process(
            {"context_id": context_id, "agent_profile": "researcher"},
            request=None,  # type: ignore[arg-type]
        )

        assert response["ok"] is True
        assert context.config.profile == "researcher"
        assert context.agent0.config.profile == "researcher"
        assert child.config.profile == "developer"
        assert requested_scopes == [project_name]
    finally:
        AgentContext.remove(context_id)


@pytest.mark.asyncio
async def test_agent_profile_set_allows_switch_during_run(monkeypatch) -> None:
    import api.agent_profile_set as agent_profile_set

    monkeypatch.setattr(
        agent_profile_set.subagents,
        "get_agents_dict",
        lambda scope: {"researcher": SimpleNamespace(title="Researcher", enabled=True)},
    )
    monkeypatch.setattr(
        agent_profile_set,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", "agent0"),
        ),
    )
    monkeypatch.setattr(agent_profile_set, "save_tmp_chat", lambda _context: None)
    monkeypatch.setattr(
        agent_profile_set,
        "mark_dirty_for_context",
        lambda *_args, **_kwargs: None,
    )

    context_id = "ctx-profile-switch-running"
    AgentContext.remove(context_id)
    context = AgentContext(
        config=AgentConfig(mcp_servers="", profile="agent0"),
        id=context_id,
        set_current=False,
    )
    started = threading.Event()
    release = threading.Event()

    async def block_run() -> None:
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.02)

    context.task = DeferredTask().start_task(block_run)
    try:
        assert started.wait(2)
        assert context.is_running()

        handler = agent_profile_set.SetAgentProfile.__new__(
            agent_profile_set.SetAgentProfile
        )
        response = await handler.process(
            {"context_id": context_id, "agent_profile": "researcher"},
            request=None,  # type: ignore[arg-type]
        )

        assert response["ok"] is True
        assert context.config.profile == "researcher"
        assert context.agent0.config.profile == "researcher"
    finally:
        release.set()
        if context.task:
            try:
                context.task.result_sync(timeout=2)
            except Exception:
                pass
        AgentContext.remove(context_id)
