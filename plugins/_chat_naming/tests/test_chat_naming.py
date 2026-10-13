import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import AgentContextType
from helpers import yaml
from plugins._chat_naming.commands import rename_command
from plugins._chat_naming.extensions.python.monologue_end import _60_rename_chat as rename_chat
from plugins._chat_naming.helpers import naming


pytestmark = pytest.mark.asyncio


class _Message:
    def __init__(self, content, *, ai=False, sequence=0):
        self.content = content
        self.ai = ai
        self.sequence = sequence


class _History:
    def __init__(self, messages):
        self._messages = messages

    def all_messages(self):
        return list(self._messages)


class _Agent:
    def __init__(self, messages, *, name="", response="Generated Name"):
        self.context = SimpleNamespace(
            id="ctx-naming",
            name=name,
            type=AgentContextType.USER,
        )
        self.context.agent0 = self
        self.context.output_data = {}
        self.context.data = {}
        self.context.get_output_data = self.context.output_data.get
        self.context.get_data = lambda key, recursive=True: self.context.data.get(key)
        self.context.set_data = lambda key, value, recursive=True: self.context.data.__setitem__(
            key, value
        )
        self.history = _History(messages)
        self.config = SimpleNamespace(profile="agent0")
        self._response = response
        self.utility_calls = []

    def read_prompt(self, name, **kwargs):
        return f"{name}:{kwargs}"

    async def call_utility_model(self, **kwargs):
        self.utility_calls.append(kwargs)
        return self._response


async def test_user_message_selection_excludes_assistant_work_and_tool_results():
    agent = _Agent(
        [
            _Message({"user_message": "Plan a launch"}, sequence=1),
            _Message({"tool_name": "search", "tool_result": "internal work"}, sequence=2),
            _Message("assistant response", ai=True, sequence=3),
            _Message({"user_intervention": "Okay, do it"}, sequence=4),
        ]
    )

    assert naming.get_user_messages(agent) == ["Plan a launch", "Okay, do it"]
    assert naming.latest_user_sequence(agent) == 4


@pytest.mark.parametrize("mode", ["once", "always"])
async def test_automatic_naming_preserves_delegated_labels(monkeypatch, mode):
    agent = _Agent([_Message({"user_message": "Investigate the issue"})], name="A1-summoner")
    agent.context.output_data.update(parent_context_id="parent", parent_context_label="A1-summoner")
    monkeypatch.setattr(naming, "get_config", lambda _agent: {
        "automatic_naming": True, "automatic_naming_mode": mode,
    })
    scheduled = []
    monkeypatch.setattr(rename_chat.asyncio, "create_task", scheduled.append)
    await rename_chat.RenameChat(agent=agent).execute()
    assert not scheduled
    assert agent.context.name == agent.context.output_data["parent_context_label"] == "A1-summoner"


async def test_once_mode_uses_first_message_and_does_not_override_a_name(monkeypatch):
    scheduled = []
    agent = _Agent(
        [
            _Message({"user_message": "First request"}, sequence=1),
            _Message({"user_message": "Second request"}, sequence=2),
        ]
    )
    monkeypatch.setattr(
        rename_chat.naming,
        "get_config",
        lambda _agent: {"automatic_naming": True, "automatic_naming_mode": "once"},
    )
    monkeypatch.setattr(rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro))

    await rename_chat.RenameChat(agent=agent).execute()
    assert len(scheduled) == 1

    captured = {}

    async def generate(_agent, **kwargs):
        captured.update(kwargs)
        return "First Request"

    saved = []
    monkeypatch.setattr(rename_chat.naming, "generate_name", generate)
    monkeypatch.setattr(
        rename_chat.naming,
        "save_context_name",
        lambda _agent, name: saved.append(name),
    )
    monkeypatch.setattr(rename_chat.AgentContext, "get", lambda _id: agent.context)
    await scheduled.pop()

    assert captured["user_messages"] == ["First request"]
    assert saved == ["First Request"]

    agent.context.name = "Manual Name"
    await rename_chat.RenameChat(agent=agent).execute()
    assert scheduled == []


@pytest.mark.parametrize("config", ["default", {}, {"automatic_naming_mode": "always"}])
async def test_default_and_always_modes_update_a_greeting_from_recent_context(monkeypatch, config):
    messages = [
        _Message({"user_message": f"Message {number}"}, sequence=number)
        for number in range(1, 6)
    ]
    messages.append(_Message({"user_message": "Explain Docker"}, sequence=6))
    agent = _Agent(messages, name="Greeting")
    if config == "default":
        config = yaml.loads(
            (Path(naming.__file__).parents[1] / "default_config.yaml").read_text()
        )
    scheduled = []
    monkeypatch.setattr(
        naming.plugins,
        "get_plugin_config",
        lambda *_args, **_kwargs: config,
    )
    monkeypatch.setattr(rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro))

    await rename_chat.RenameChat(agent=agent).execute()
    captured = {}

    async def generate(_agent, **kwargs):
        captured.update(kwargs)
        return "Current Topic"

    monkeypatch.setattr(rename_chat.naming, "generate_name", generate)
    saved = []
    monkeypatch.setattr(rename_chat.naming, "save_context_name", lambda _agent, name: saved.append(name))
    monkeypatch.setattr(rename_chat.AgentContext, "get", lambda _id: agent.context)
    await scheduled.pop()

    assert captured["user_messages"] == [
        "Message 3",
        "Message 4",
        "Message 5",
        "Explain Docker",
    ]
    assert captured["current_name"] == "Greeting"
    assert saved == ["Current Topic"]


async def test_naming_hook_returns_while_utility_inference_is_pending(monkeypatch):
    agent = _Agent([_Message({"user_message": "Explain Docker"}, sequence=1)], name="Greeting")
    started = asyncio.Event()
    release = asyncio.Event()
    running = []
    saved = []

    async def slow_utility(**kwargs):
        assert kwargs["background"] is True
        running.append(asyncio.current_task())
        started.set()
        await release.wait()
        return "Docker Explanation"

    monkeypatch.setattr(agent, "call_utility_model", slow_utility)
    monkeypatch.setattr(naming.plugins, "get_plugin_config", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.get_utility_model_config",
        lambda _agent: {"ctx_length": 1000},
    )
    monkeypatch.setattr(rename_chat.AgentContext, "get", lambda _id: agent.context)
    monkeypatch.setattr(naming, "save_context_name", lambda _agent, name: saved.append(name))

    try:
        await asyncio.wait_for(rename_chat.RenameChat(agent=agent).execute(), timeout=1)
        await asyncio.wait_for(started.wait(), timeout=1)
        assert not running[0].done()
        assert saved == []
    finally:
        release.set()
        await asyncio.gather(*running, return_exceptions=True)

    assert saved == ["Docker Explanation"]


async def test_rename_failure_sends_scoped_utility_model_notification(monkeypatch):
    sent = []
    agent = _Agent([_Message({"user_message": "Plan a launch"}, sequence=1)])

    async def fail(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(rename_chat.naming, "generate_name", fail)
    monkeypatch.setattr(
        rename_chat.NotificationManager,
        "send_notification",
        lambda **kwargs: sent.append(kwargs),
    )

    await rename_chat.RenameChat(agent=agent).change_name(
        messages=["Plan a launch"],
        request_sequence=1,
        only_if_unnamed=True,
    )

    assert len(sent) == 1
    assert sent[0]["type"] == rename_chat.NotificationType.ERROR
    assert sent[0]["title"] == "Chat Naming Failed"
    assert sent[0]["id"] == "chat_naming_failed_ctx-naming"


async def test_generated_name_is_normalized_and_bounded(monkeypatch):
    agent = _Agent(
        [_Message({"user_message": "Plan the release"}, sequence=1)],
        response='  "A very long generated release planning title that should be shortened"  ',
    )
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.get_utility_model_config",
        lambda _agent: {"ctx_length": 1000},
    )

    result = await naming.generate_name(agent)

    assert len(result) <= naming.GENERATED_NAME_LIMIT
    assert result.endswith("...")
    assert agent.utility_calls[0]["background"] is True


async def test_naming_input_stays_within_utility_context_budget(monkeypatch):
    agent = _Agent(
        [
            _Message({"user_message": "older context " * 2000}, sequence=1),
            _Message({"user_message": "LATEST_CONTEXT " * 2000}, sequence=2),
        ],
        response="Budgeted Name",
    )
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.get_utility_model_config",
        lambda _agent: {"ctx_length": 300},
    )

    await naming.generate_name(agent)

    call = agent.utility_calls[0]
    estimated_tokens = naming.tokens.approximate_tokens(
        call["system"]
    ) + naming.tokens.approximate_tokens(call["message"])
    assert estimated_tokens <= int(300 * naming.UTILITY_CONTEXT_INPUT_RATIO)
    assert "LATEST_CONTEXT" in call["message"]
    assert "older context" not in call["message"]


async def test_manual_api_generates_and_saves_with_target_chat_agent(monkeypatch):
    from plugins._chat_naming.api import chat_name

    agent = _Agent([_Message({"user_message": "Name this chat"}, sequence=1)])
    monkeypatch.setattr(chat_name.AgentContext, "get", lambda _id: agent.context)

    async def generate(target_agent, **kwargs):
        assert target_agent is agent
        assert kwargs["current_name"] == ""
        return "Generated Chat"

    saved = []
    monkeypatch.setattr(chat_name.naming, "generate_name", generate)
    monkeypatch.setattr(
        chat_name.naming,
        "save_context_name",
        lambda target_agent, name: saved.append((target_agent, name)),
    )
    handler = object.__new__(chat_name.ChatName)

    generated = await handler.process(
        {"action": "generate", "kind": "chat", "item_id": agent.context.id},
        None,
    )
    renamed = await handler.process(
        {
            "action": "save",
            "kind": "chat",
            "item_id": agent.context.id,
            "name": "  Manual   Chat  ",
        },
        None,
    )

    assert generated == {"ok": True, "name": "Generated Chat"}
    assert renamed == {"ok": True, "name": "Manual Chat"}
    assert saved == [(agent, "Manual Chat")]


async def test_rename_command_saves_a_custom_name(monkeypatch):
    agent = _Agent([_Message({"user_message": "Plan a launch"}, sequence=1)])
    saved = []
    monkeypatch.setattr(
        rename_command.naming,
        "save_context_name",
        lambda target_agent, name: saved.append((target_agent, name)) or name,
    )

    result = await rename_command.run(
        {
            "invocation": {"raw_arguments": "New Chat Name"},
            "context": {"agent": agent},
        }
    )

    assert saved == [(agent, "New Chat Name")]
    assert result == {
        "text": "",
        "effects": [
            {
                "type": "toast",
                "message": 'Chat renamed to "New Chat Name".',
                "level": "success",
            }
        ],
    }


async def test_rejected_rename_does_not_disable_automatic_naming():
    agent = _Agent([], name="Automatic Name")

    with pytest.raises(ValueError, match="200 characters"):
        await rename_command.run(
            {
                "invocation": {"raw_arguments": "x" * 201},
                "context": {"agent": agent},
            }
        )

    assert agent.context.name == "Automatic Name"
    assert agent.context.get_data(naming.MANUAL_NAME_KEY) is None


async def test_rename_auto_generates_and_saves_a_name(monkeypatch):
    agent = _Agent([_Message({"user_message": "Plan a launch"}, sequence=1)])
    generated = []
    saved = []

    async def generate(target_agent):
        generated.append(target_agent)
        return "Launch Plan"

    monkeypatch.setattr(rename_command.naming, "generate_name", generate)
    monkeypatch.setattr(
        rename_command.naming,
        "save_context_name",
        lambda target_agent, name: saved.append((target_agent, name)) or name,
    )

    result = await rename_command.run(
        {
            "invocation": {"raw_arguments": "auto"},
            "context": {"agent": agent},
        }
    )

    assert generated == [agent]
    assert saved == [(agent, "Launch Plan")]
    assert result["effects"][0]["message"] == 'Chat renamed to "Launch Plan".'


async def test_manual_task_rename_updates_scheduler_and_context(monkeypatch):
    from plugins._chat_naming.api import chat_name

    agent = _Agent([_Message({"user_message": "Run a report"}, sequence=1)], name="Old Task")

    class _Scheduler:
        def __init__(self):
            self.updated = []

        async def reload(self):
            return None

        async def update_task(self, item_id, **kwargs):
            self.updated.append((item_id, kwargs))
            return SimpleNamespace(name=kwargs["name"])

    scheduler = _Scheduler()
    saved = []
    dirty = []
    monkeypatch.setattr(chat_name.AgentContext, "get", lambda _id: agent.context)
    monkeypatch.setattr(chat_name.TaskScheduler, "get", lambda: scheduler)
    monkeypatch.setattr(
        chat_name,
        "save_tmp_chat",
        lambda context: saved.append(
            (context.name, context.get_data(naming.MANUAL_NAME_KEY))
        ),
    )
    monkeypatch.setattr(chat_name, "mark_dirty_all", lambda *, reason: dirty.append(reason))

    response = await object.__new__(chat_name.ChatName).process(
        {
            "action": "save",
            "kind": "task",
            "item_id": agent.context.id,
            "name": "Daily Report",
        },
        None,
    )

    assert response == {"ok": True, "name": "Daily Report"}
    assert scheduler.updated == [(agent.context.id, {"name": "Daily Report"})]
    assert agent.context.name == "Daily Report"
    assert saved == [("Daily Report", True)]
    assert agent.context.data[naming.MANUAL_NAME_KEY] is True
    assert dirty == ["plugins._chat_naming.save_task_name"]


async def test_chat_naming_endpoints_keep_default_auth_and_csrf_protection():
    from plugins._chat_naming.api.chat_name import ChatName

    assert ChatName.requires_auth() is True
    assert ChatName.requires_csrf() is True


async def test_always_mode_does_not_schedule_or_save_after_manual_name(monkeypatch):
    """A name set with /rename must not be replaced by always-mode auto-naming (#1941)."""
    agent = _Agent(
        [_Message({"user_message": "Explain Docker networking"}, sequence=1)],
        response="Docker Networking",
    )
    monkeypatch.setattr(naming.persist_chat, "save_tmp_chat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(naming, "mark_dirty_all", lambda **_kwargs: None)
    monkeypatch.setattr(
        "plugins._model_config.helpers.model_config.get_utility_model_config",
        lambda _agent: {"ctx_length": 1000},
    )
    monkeypatch.setattr(
        naming.plugins,
        "get_plugin_config",
        lambda *_args, **_kwargs: {
            "automatic_naming": True,
            "automatic_naming_mode": "always",
        },
    )

    await rename_command.run(
        {
            "invocation": {"raw_arguments": "Manual Name"},
            "context": {"agent": agent},
        }
    )
    assert agent.context.name == "Manual Name"
    assert agent.context.data[naming.MANUAL_NAME_KEY] is True

    scheduled = []
    monkeypatch.setattr(
        rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro)
    )
    await rename_chat.RenameChat(agent=agent).execute()
    monkeypatch.setattr(rename_chat.AgentContext, "get", lambda _id: agent.context)
    if scheduled:
        await scheduled[0]

    if scheduled and agent.context.name != "Manual Name":
        pytest.fail(
            "BUG_REPRODUCED: always-mode scheduled auto-naming and saved "
            f"{agent.context.name!r} over the manual name"
        )
    assert scheduled == []
    assert agent.context.name == "Manual Name"


async def test_api_save_sets_manual_flag_and_blocks_always_mode(monkeypatch):
    from plugins._chat_naming.api import chat_name

    agent = _Agent(
        [_Message({"user_message": "Name this chat"}, sequence=1)],
        name="Greeting",
    )
    monkeypatch.setattr(chat_name.AgentContext, "get", lambda _id: agent.context)
    monkeypatch.setattr(naming.persist_chat, "save_tmp_chat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(naming, "mark_dirty_all", lambda **_kwargs: None)

    response = await object.__new__(chat_name.ChatName).process(
        {
            "action": "save",
            "kind": "chat",
            "item_id": agent.context.id,
            "name": "  Manual   Chat  ",
        },
        None,
    )

    assert response == {"ok": True, "name": "Manual Chat"}
    assert agent.context.name == "Manual Chat"
    assert agent.context.data[naming.MANUAL_NAME_KEY] is True

    scheduled = []
    monkeypatch.setattr(
        naming.plugins,
        "get_plugin_config",
        lambda *_args, **_kwargs: {
            "automatic_naming": True,
            "automatic_naming_mode": "always",
        },
    )
    monkeypatch.setattr(
        rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro)
    )
    await rename_chat.RenameChat(agent=agent).execute()
    assert scheduled == []
    assert agent.context.name == "Manual Chat"


async def test_rename_auto_clears_manual_flag_and_allows_always_mode(monkeypatch):
    agent = _Agent(
        [_Message({"user_message": "Plan a launch"}, sequence=1)],
        name="Manual Name",
    )
    agent.context.set_data(naming.MANUAL_NAME_KEY, True)
    monkeypatch.setattr(naming.persist_chat, "save_tmp_chat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(naming, "mark_dirty_all", lambda **_kwargs: None)

    async def generate(target_agent):
        assert target_agent is agent
        return "Launch Plan"

    monkeypatch.setattr(rename_command.naming, "generate_name", generate)
    result = await rename_command.run(
        {
            "invocation": {"raw_arguments": "auto"},
            "context": {"agent": agent},
        }
    )

    assert agent.context.get_data(naming.MANUAL_NAME_KEY) is False
    assert agent.context.name == "Launch Plan"
    assert result["effects"][0]["message"] == 'Chat renamed to "Launch Plan".'

    scheduled = []
    monkeypatch.setattr(
        naming.plugins,
        "get_plugin_config",
        lambda *_args, **_kwargs: {
            "automatic_naming": True,
            "automatic_naming_mode": "always",
        },
    )
    monkeypatch.setattr(
        rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro)
    )
    await rename_chat.RenameChat(agent=agent).execute()
    assert len(scheduled) == 1
    scheduled[0].close()


async def test_name_change_while_pending_does_not_overwrite(monkeypatch):
    agent = _Agent(
        [_Message({"user_message": "Explain Docker"}, sequence=6)],
        name="Greeting",
    )
    scheduled = []
    monkeypatch.setattr(
        naming.plugins,
        "get_plugin_config",
        lambda *_args, **_kwargs: {
            "automatic_naming": True,
            "automatic_naming_mode": "always",
        },
    )
    monkeypatch.setattr(
        rename_chat.asyncio, "create_task", lambda coro: scheduled.append(coro)
    )
    await rename_chat.RenameChat(agent=agent).execute()
    assert len(scheduled) == 1

    async def generate(_agent, **kwargs):
        _agent.context.name = "Manual Name"
        return "Utility Name"

    saved = []
    monkeypatch.setattr(rename_chat.naming, "generate_name", generate)
    monkeypatch.setattr(
        rename_chat.naming,
        "save_context_name",
        lambda _agent, name: saved.append(name),
    )
    monkeypatch.setattr(rename_chat.AgentContext, "get", lambda _id: agent.context)
    await scheduled.pop()

    assert saved == []
    assert agent.context.name == "Manual Name"
