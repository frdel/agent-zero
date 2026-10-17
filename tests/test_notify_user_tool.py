import pytest
from types import SimpleNamespace

import plugins._notify_user.tools.notify_user as notify_user_module
from helpers.notification import NotificationPriority
from helpers.tool import Response
from plugins._notify_user.tools.notify_user import NotifyUserTool


class _FakeLog:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def log(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return kwargs


class _FakeAgent:
    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())

    def read_prompt(self, name: str, **kwargs) -> str:
        return "sent"


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add_notification(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _make_tool(args: dict, manager: _FakeNotificationManager, monkeypatch) -> NotifyUserTool:
    monkeypatch.setattr(
        notify_user_module.AgentContext,
        "get_notification_manager",
        classmethod(lambda cls: manager),
    )
    return NotifyUserTool(
        agent=_FakeAgent(), name="notify_user", method="execute", args=args, message="notify", loop_data=None
    )


@pytest.mark.anyio
async def test_execute_defaults_to_high_priority(monkeypatch):
    manager = _FakeNotificationManager()
    tool = _make_tool({"message": "hello"}, manager, monkeypatch)

    response = await tool.execute()

    assert isinstance(response, Response)
    assert response.break_loop is False
    assert len(manager.calls) == 1
    assert manager.calls[0]["priority"] is NotificationPriority.HIGH
    assert manager.calls[0]["message"] == "hello"
    assert manager.calls[0]["display_time"] == 30


@pytest.mark.anyio
async def test_execute_maps_priority_names(monkeypatch):
    manager = _FakeNotificationManager()
    tool = _make_tool({"message": "hi", "priority": "normal"}, manager, monkeypatch)

    await tool.execute()

    assert manager.calls[0]["priority"] is NotificationPriority.NORMAL


@pytest.mark.anyio
async def test_execute_rejects_unknown_priority(monkeypatch):
    manager = _FakeNotificationManager()
    tool = _make_tool({"message": "hi", "priority": "urgent"}, manager, monkeypatch)

    response = await tool.execute()

    assert response.message == "Invalid notification priority: urgent"
    assert response.break_loop is False
    assert manager.calls == []


@pytest.mark.anyio
async def test_execute_rejects_invalid_type(monkeypatch):
    manager = _FakeNotificationManager()
    tool = _make_tool({"message": "hi", "type": "banana"}, manager, monkeypatch)

    response = await tool.execute()

    assert response.message == "Invalid notification type: banana"
    assert response.break_loop is False
    assert manager.calls == []


@pytest.mark.anyio
async def test_execute_requires_message(monkeypatch):
    manager = _FakeNotificationManager()
    tool = _make_tool({}, manager, monkeypatch)

    response = await tool.execute()

    assert response.message == "Message is required"
    assert response.break_loop is False
    assert manager.calls == []


def test_get_heading_prefers_title_with_notification_icon():
    tool = NotifyUserTool(
        agent=_FakeAgent(), name="notify_user", method="execute", args={"title": "Deploy done"}, message="notify", loop_data=None
    )

    assert tool.get_heading() == "icon://notifications Notifying user: Deploy done"


def test_get_heading_falls_back_without_title():
    tool = NotifyUserTool(
        agent=_FakeAgent(), name="notify_user", method="execute", args={}, message="notify", loop_data=None
    )

    assert tool.get_heading() == "icon://notifications Notifying user"


def test_log_object_passes_title_through():
    agent = _FakeAgent()
    tool = NotifyUserTool(
        agent=agent, name="notify_user", method="execute", args={"message": "hi", "title": "Deploy"}, message="notify", loop_data=None
    )

    entry = tool.get_log_object()

    assert entry["type"] == "notify_user"
    assert entry["heading"] == "icon://notifications Notifying user: Deploy"
    assert entry["kvps"]["title"] == "Deploy"
    assert entry["kvps"]["message"] == "hi"
