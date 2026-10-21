import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import Agent, AgentConfig, AgentContext, UserMessage
from helpers import extension, persist_chat, task_scheduler as scheduler
from helpers.llm_result import LLMResult


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    point = "_functions/agent/Agent/monologue/end"
    hooks = extension._get_extensions(str(PROJECT_ROOT / "extensions/python" / point))
    assert any(hook.__name__ == "UpdateSchedulerTask" for hook in hooks)
    monkeypatch.setattr(
        extension, "_get_extension_classes",
        lambda name, **kwargs: hooks if name == point else [],
    )
    monkeypatch.setattr(AgentContext, "_contexts", {})
    monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(tmp_path / "scheduler"))
    monkeypatch.setattr(persist_chat, "CHATS_FOLDER", str(tmp_path / "chats"))
    monkeypatch.setattr(scheduler.TaskScheduler, "_instance", None)
    monkeypatch.setattr(scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None)
    monkeypatch.setattr("helpers.state_monitor_integration.mark_dirty_all", lambda **kwargs: None)
    config = AgentConfig(mcp_servers="")
    monkeypatch.setattr(scheduler, "initialize_agent", lambda: config)
    monkeypatch.setattr(persist_chat, "initialize_agent", lambda **kwargs: config)
    now = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_now", lambda: now)

    deferred = []
    deferred_class = scheduler.DeferredTask

    def capture_task(**kwargs):
        task = deferred_class(**kwargs)
        deferred.append(task)
        return task

    monkeypatch.setattr(scheduler, "DeferredTask", capture_task)

    def model(agent, *outcomes):
        agent.prepare_prompt = AsyncMock(return_value=[])
        agent.handle_intervention = AsyncMock()
        agent.call_chat_model_turn = AsyncMock(side_effect=[
            value if isinstance(value, BaseException) else LLMResult(response=value)
            for value in outcomes
        ])
        agent.process_llm_result_tools = AsyncMock(side_effect=lambda result: result.response)

    return SimpleNamespace(
        engine=scheduler.TaskScheduler.get(), model=model, deferred=deferred, now=now,
    )


@pytest.mark.parametrize("task_type", ["adhoc", "scheduled", "planned"])
@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("file_format", ["json", "yaml"])
def test_failed_scheduler_task_recovers_through_restored_chat(runtime, monkeypatch, task_type, shared, file_format):
    engine = runtime.engine
    if file_format == "yaml":
        path = Path(scheduler.SCHEDULER_FOLDER, "tasks.json")
        path.rename(path.with_suffix(".yaml"))
    common = dict(name="Recovery", system_prompt="", prompt="Work", context_id="shared" if shared else None)
    if task_type == "planned":
        task = scheduler.PlannedTask(**common, plan=scheduler.TaskPlan(todo=[runtime.now - timedelta(minutes=1)]))
    elif task_type == "scheduled":
        task = scheduler.ScheduledTask(**common, schedule=scheduler.TaskSchedule(
            minute="0", hour="9", day="*", month="*", weekday="*", timezone="UTC",
        ))
    else:
        task = scheduler.AdHocTask(**common)
    asyncio.run(engine.add_task(task))
    context = AgentContext.get(task.context_id)
    runtime.model(context.agent0, RuntimeError("simulated model failure"))

    asyncio.run(engine.run_task_by_uuid(task.uuid))
    runtime.deferred[-1].result_sync(timeout=5)
    asyncio.run(engine.reload())
    failed = engine.get_task_by_uuid(task.uuid)
    assert failed.state == scheduler.TaskState.ERROR
    assert "simulated model failure" in failed.last_result
    plan = failed.plan.model_dump() if task_type == "planned" else None
    if plan is not None:
        assert plan["todo"] == [] and plan["in_progress"] is None
        assert len(plan["done"]) == 1

    # Restore the saved chat before continuing, as after a framework restart.
    context = persist_chat._deserialize_context(
        json.loads(Path(persist_chat._get_chat_file_path(context.id)).read_text())
    )
    assert context.get_data("scheduler_task_uuid") == task.uuid
    recovered_at = runtime.now + timedelta(minutes=5)
    monkeypatch.setattr(scheduler, "_now", lambda: recovered_at)
    runtime.model(context.agent0, "Recovered", "Follow-up completed")
    assert context.communicate(UserMessage("Continue")).result_sync(timeout=5) == "Recovered"
    assert context.communicate(UserMessage("Next step")).result_sync(timeout=5) == "Follow-up completed"

    asyncio.run(engine.reload())
    recovered = engine.get_task_by_uuid(task.uuid)
    assert recovered.state == scheduler.TaskState.IDLE
    assert recovered.last_result == "Recovered"
    assert recovered.last_run == recovered_at
    if plan is not None:
        assert recovered.plan.model_dump() == plan


@pytest.mark.parametrize("state", list(scheduler.TaskState))
def test_chat_completion_only_recovers_its_errored_task(runtime, state):
    engine = runtime.engine
    context = AgentContext(AgentConfig(mcp_servers=""), id="shared")
    owner = scheduler.AdHocTask(name="Owner", system_prompt="", prompt="", context_id=context.id, state=state)
    other = scheduler.AdHocTask(name="Other", system_prompt="", prompt="", context_id=context.id, state=scheduler.TaskState.ERROR)
    asyncio.run(engine._tasks.add_task(owner))
    asyncio.run(engine._tasks.add_task(other))
    context.set_data("scheduler_task_uuid", owner.uuid)
    runtime.model(context.agent0, "Done")

    assert context.communicate(UserMessage("Continue")).result_sync(timeout=5) == "Done"
    asyncio.run(engine.reload())
    current = engine.get_task_by_uuid(owner.uuid)
    assert current.state == (scheduler.TaskState.IDLE if state == scheduler.TaskState.ERROR else state)
    assert current.last_result == ("Done" if state == scheduler.TaskState.ERROR else None)
    assert engine.get_task_by_uuid(other.uuid).state == scheduler.TaskState.ERROR


@pytest.mark.parametrize("outcome", [RuntimeError("Still failing"), asyncio.CancelledError()])
def test_failed_or_cancelled_chat_does_not_clear_error(runtime, outcome):
    task = scheduler.AdHocTask(name="Failed", system_prompt="", prompt="", state=scheduler.TaskState.ERROR, last_result="Original error")
    asyncio.run(runtime.engine.add_task(task))
    context = AgentContext.get(task.context_id)
    runtime.model(context.agent0, outcome)
    with pytest.raises(type(outcome)):
        asyncio.run(context._process_chain(context.agent0, UserMessage("Continue")))
    asyncio.run(runtime.engine.reload())
    current = runtime.engine.get_task_by_uuid(task.uuid)
    assert current.state == scheduler.TaskState.ERROR
    assert current.last_result == "Original error"


def test_legacy_dedicated_chat_recovers_but_shared_chat_is_ambiguous(runtime):
    for shared in (False, True):
        task = scheduler.AdHocTask(name="Legacy", system_prompt="", prompt="", state=scheduler.TaskState.ERROR, context_id="shared" if shared else None)
        asyncio.run(runtime.engine.add_task(task))
        context = AgentContext.get(task.context_id)
        assert context.get_data("scheduler_task_uuid") is None
        runtime.model(context.agent0, "Done")
        assert context.communicate(UserMessage("Continue")).result_sync(timeout=5) == "Done"
        asyncio.run(runtime.engine.reload())
        assert runtime.engine.get_task_by_uuid(task.uuid).state == (
            scheduler.TaskState.ERROR if shared else scheduler.TaskState.IDLE
        )


def test_subordinate_success_does_not_clear_main_task_error(runtime):
    task = scheduler.AdHocTask(name="Parent", system_prompt="", prompt="", state=scheduler.TaskState.ERROR)
    asyncio.run(runtime.engine.add_task(task))
    context = AgentContext.get(task.context_id)
    child = Agent(1, context.config, context)
    runtime.model(child, "Child finished")
    assert asyncio.run(child.monologue()) == "Child finished"
    asyncio.run(runtime.engine.reload())
    assert runtime.engine.get_task_by_uuid(task.uuid).state == scheduler.TaskState.ERROR


@pytest.mark.parametrize("change", ["remove", "reassign"])
def test_chat_completion_preserves_removed_or_reassigned_task(runtime, change):
    engine = runtime.engine
    task = scheduler.AdHocTask(name="Changed", system_prompt="", prompt="", state=scheduler.TaskState.ERROR)
    asyncio.run(engine.add_task(task))
    context = AgentContext.get(task.context_id)
    context.set_data("scheduler_task_uuid", task.uuid)
    if change == "remove":
        asyncio.run(engine.remove_task_by_uuid(task.uuid))
    else:
        asyncio.run(engine.update_task(task.uuid, context_id="another-chat"))
    runtime.model(context.agent0, "Done")
    assert context.communicate(UserMessage("Continue")).result_sync(timeout=5) == "Done"
    asyncio.run(engine.reload())
    current = engine.get_task_by_uuid(task.uuid)
    if change == "remove":
        assert current is None
    else:
        assert current.context_id == "another-chat" and current.state == scheduler.TaskState.ERROR


def test_explicit_scheduler_retry_keeps_existing_callbacks(runtime):
    engine = runtime.engine
    task = scheduler.AdHocTask(name="Retry", system_prompt="", prompt="Work")
    asyncio.run(engine.add_task(task))
    context = AgentContext.get(task.context_id)
    runtime.model(context.agent0, RuntimeError("Failure"), "Retry succeeded")
    for expected in (scheduler.TaskState.ERROR, scheduler.TaskState.IDLE):
        asyncio.run(engine.run_task_by_uuid(task.uuid))
        runtime.deferred[-1].result_sync(timeout=5)
        asyncio.run(engine.reload())
        assert engine.get_task_by_uuid(task.uuid).state == expected
    assert engine.get_task_by_uuid(task.uuid).last_result == "Retry succeeded"
