from types import SimpleNamespace
import uuid

import pytest

from agent import AgentContext, UserMessage


@pytest.fixture
def legacy_context(monkeypatch):
    from helpers.durable import runtime
    # These tests exercise ordinary task/intervention dispatch. Do not inherit
    # a recovery service from another test or admit work into a shared ledger.
    monkeypatch.setattr(runtime, "_service", None)
    context = AgentContext.__new__(AgentContext)
    # The real constructor establishes identity before any lifecycle hook.
    # Keep kill_process and connector cleanup active with an isolated chat ID.
    context.id = "test-intervention-" + uuid.uuid4().hex
    context.data = {}
    return context


def test_nudge_stops_running_context_and_starts_nudge_message(legacy_context):
    context = legacy_context
    calls = []

    class _Task:
        def is_alive(self):
            return False

        def kill(self):
            calls.append("kill")

    context.task = _Task()
    context.paused = True
    context.streaming_agent = None
    context.agent0 = SimpleNamespace(
        intervention=None,
        data={},
        read_prompt=lambda _name: "nudge text",
    )

    started = {}

    def fake_run_task(func, *args):
        assert calls == ["kill"]
        assert context.paused is False
        started["func"] = func
        started["args"] = args
        return "new-task"

    context.run_task = fake_run_task

    result = context.nudge()

    assert calls == ["kill"]
    assert result == "new-task"
    assert started["func"] == context._process_chain
    assert started["args"][0] is context.agent0
    assert started["args"][1].system_message == ["nudge text"]
    assert started["args"][1].message == ""


def test_user_message_during_run_sets_intervention(legacy_context):
    context = legacy_context

    current = SimpleNamespace(intervention=None, data={})

    context.task = SimpleNamespace(is_alive=lambda: True)
    context.paused = True
    context.streaming_agent = current
    context.agent0 = current

    message = UserMessage("intervene")
    result = context.communicate(message)

    assert current.intervention is message
    assert context.paused is False
    assert result is context.task
