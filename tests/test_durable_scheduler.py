"""Occurrence projections survive restart boundaries without callback replay."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from agent import AgentConfig, AgentContext
from helpers import extension, task_scheduler as scheduler
from helpers.durable import codec, runtime
from helpers.durable import scheduler as adapter
from helpers.durable.store import LocalStore


class Deferred:
    def kill(self, **kwargs):
        self.killed = True

    def add_done_callback(self, callback):
        self.callback = callback


class Owner:
    enabled = True
    failed = False

    def __init__(self, root):
        self.store = LocalStore(root)
        self.lock = threading.RLock()
        self.submissions = []

    def sync(self, method, *args, **kwargs):
        return getattr(self.store, method)(*args, **kwargs)

    async def io(self, method, *args, **kwargs):
        return self.sync(method, *args, **kwargs)

    def submit_owned(self, context, message, origin):
        run = self.store.admit(context.id, message.id, codec.message_payload(message), {
            "origin": origin, "context": {"id": context.id},
        })
        self.submissions.append((context, message, run))
        return Deferred()


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(extension, "call_extensions_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(AgentContext, "_contexts", {})
    monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(tmp_path / "scheduler"))
    monkeypatch.setattr(scheduler.TaskScheduler, "_instance", None)
    monkeypatch.setattr(scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None)
    monkeypatch.setattr("helpers.state_monitor_integration.mark_dirty_all", lambda **kwargs: None)
    monkeypatch.setattr(codec, "masked", lambda agent, value: value)
    config = AgentConfig(mcp_servers="")
    monkeypatch.setattr(scheduler, "initialize_agent", lambda: config)
    monkeypatch.setattr(scheduler, "save_tmp_chat", lambda context: None)
    now = datetime(2026, 10, 22, 10, 0, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_now", lambda: now)
    owner = Owner(tmp_path / "durability")
    monkeypatch.setattr(runtime, "_service", owner)
    engine = scheduler.TaskScheduler.get()
    context = AgentContext(config, id="scheduler-context")
    yield SimpleNamespace(owner=owner, engine=engine, context=context, now=now, root=tmp_path)
    owner.store.close()


def add(env, kind="adhoc"):
    common = dict(name="Work", prompt="Do work", system_prompt="System", context_id=env.context.id)
    if kind == "planned":
        task = scheduler.PlannedTask(**common, plan=scheduler.TaskPlan(todo=[
            env.now - timedelta(minutes=1), env.now + timedelta(hours=1),
        ]))
    elif kind == "scheduled":
        task = scheduler.ScheduledTask(**common, schedule=scheduler.TaskSchedule(
            minute="*", hour="*", day="*", month="*", weekday="*", timezone="UTC"))
    else:
        task = scheduler.AdHocTask(**common)
    asyncio.run(env.engine._tasks.add_task(task))
    return task


def submitted(env, task):
    asyncio.run(env.engine._run_task(task))
    return env.owner.submissions[-1][2]


@pytest.mark.parametrize("kind", ["adhoc", "scheduled", "planned"])
@pytest.mark.parametrize("file_format", ["json", "yaml"])
def test_prepare_and_completion_reconcile_after_projection_before_journal(env, monkeypatch, kind, file_format):
    task = add(env, kind)
    if file_format == "yaml":
        path = Path(scheduler.SCHEDULER_FOLDER, "tasks.json")
        # Write the supported representation rather than simply rename JSON.
        from helpers import yaml
        path.with_suffix(".yaml").write_text(yaml.from_json(path.read_text()))
        path.unlink()
    run = submitted(env, task)
    original = env.owner.io
    cut = {"label": "scheduler:prepare"}

    async def crash_after_projection(method, *args, **kwargs):
        if method == "start_call" and args[1] == cut["label"]:
            raise RuntimeError("process ended after task projection")
        return await original(method, *args, **kwargs)

    monkeypatch.setattr(env.owner, "io", crash_after_projection)
    with pytest.raises(RuntimeError):
        asyncio.run(adapter.prepare(env.owner, env.context, run))
    asyncio.run(env.engine.reload())
    prepared = env.engine.get_task_by_uuid(task.uuid)
    assert prepared.state == scheduler.TaskState.RUNNING
    if kind == "planned":
        assert len(prepared.plan.todo) == 1 and prepared.plan.in_progress is not None
    # A fresh coordinator repeats preparation; it does not claim another launch.
    monkeypatch.setattr(env.owner, "io", original)
    asyncio.run(adapter.prepare(env.owner, env.context, run))
    cut["label"] = "scheduler:complete"
    monkeypatch.setattr(env.owner, "io", crash_after_projection)
    with pytest.raises(RuntimeError):
        asyncio.run(adapter.complete(env.owner, env.context, run, "Done"))
    monkeypatch.setattr(env.owner, "io", original)
    asyncio.run(adapter.complete(env.owner, env.context, run, "Done"))
    asyncio.run(env.engine.reload())
    complete = env.engine.get_task_by_uuid(task.uuid)
    assert complete.state == scheduler.TaskState.IDLE and complete.last_result == "Done"
    assert complete.durable_finished_occurrence_id == run["checkpoint"]["origin"]["occurrence_id"]
    if kind == "planned":
        assert len(complete.plan.done) == 1 and len(complete.plan.todo) == 1
        assert complete.plan.in_progress is None
    assert env.owner.store.get_call(run["run_id"], "scheduler:complete")["status"] == "completed"
    # Private receipt fields never appear in the scheduler UI/API projection.
    assert not any(key.startswith("durable_") for key in scheduler.serialize_task(complete))


def test_tick_deduplicates_a_due_occurrence_before_prepare(env):
    task = add(env, "scheduled")
    asyncio.run(env.engine.tick())
    asyncio.run(env.engine.tick())
    assert len(env.owner.submissions) == 2
    assert env.owner.submissions[0][1].id == env.owner.submissions[1][1].id
    assert env.owner.submissions[0][2]["run_id"] == env.owner.submissions[1][2]["run_id"]
    assert len(env.owner.store.list_run_headers(context_id=env.context.id)) == 1
    assert env.context.agent0.history.all_messages() == []
    assert env.context.get_data("scheduler_task_uuid") == task.uuid


@pytest.mark.parametrize("status,state", [("cancelled", scheduler.TaskState.IDLE), ("attention", scheduler.TaskState.ERROR)])
def test_stop_and_attention_finish_only_the_owning_plan_once(env, status, state):
    task = add(env, "planned")
    run = submitted(env, task)
    asyncio.run(adapter.prepare(env.owner, env.context, run))
    asyncio.run(adapter.halted(env.owner, env.context, run, status))
    asyncio.run(adapter.halted(env.owner, env.context, run, status))
    asyncio.run(env.engine.reload())
    current = env.engine.get_task_by_uuid(task.uuid)
    assert current.state == state
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1
    with pytest.raises(runtime.RecoveryHeld, match="already_stopped"):
        asyncio.run(adapter.complete(env.owner, env.context, run, "Late success"))


@pytest.mark.parametrize("change", ["remove", "reassign", "disable"])
def test_completion_preserves_removed_reassigned_or_disabled_task(env, change):
    task = add(env)
    run = submitted(env, task)
    asyncio.run(adapter.prepare(env.owner, env.context, run))
    if change == "remove":
        asyncio.run(env.engine.remove_task_by_uuid(task.uuid))
    elif change == "reassign":
        asyncio.run(env.engine.update_task(task.uuid, context_id="other"))
    else:
        asyncio.run(env.engine.update_task(task.uuid, state=scheduler.TaskState.DISABLED))
    asyncio.run(adapter.complete(env.owner, env.context, run, "Done"))
    asyncio.run(adapter.complete(env.owner, env.context, run, "Done"))
    asyncio.run(env.engine.reload())
    current = env.engine.get_task_by_uuid(task.uuid)
    assert current is None if change == "remove" else current.last_result is None
    assert env.owner.store.get_call(run["run_id"], "scheduler:complete")["result"]["skipped"] is True


@pytest.mark.parametrize("kind", ["adhoc", "scheduled", "planned"])
def test_custom_callbacks_are_held_before_admission(env, monkeypatch, kind):
    task = add(env, kind)
    invoked = []

    async def custom_success(self, result):
        invoked.append(result)

    monkeypatch.setattr(scheduler.BaseTask, "on_success", custom_success)
    with pytest.raises(runtime.RecoveryHeld, match="callback_adapter_required"):
        submitted(env, task)
    assert invoked == [] and env.owner.submissions == []


def test_changed_task_configuration_holds_before_model_execution(env):
    task = add(env)
    run = submitted(env, task)
    asyncio.run(env.engine.update_task(task.uuid, prompt="Changed"))
    with pytest.raises(runtime.RecoveryHeld, match="configuration_changed"):
        asyncio.run(adapter.prepare(env.owner, env.context, run))
    asyncio.run(env.engine.reload())
    assert env.engine.get_task_by_uuid(task.uuid).state == scheduler.TaskState.IDLE


def test_disabled_backend_cannot_bypass_a_durable_scheduler_owner(env):
    task = add(env)
    submitted(env, task)
    env.owner.enabled = False
    with pytest.raises(RuntimeError, match="owns this scheduler context"):
        asyncio.run(env.engine._run_task(task))


def test_rejected_retry_keeps_errored_occurrence_projection(env):
    task = add(env)
    run = submitted(env, task)
    asyncio.run(adapter.prepare(env.owner, env.context, run))
    asyncio.run(adapter.halted(env.owner, env.context, run, "attention"))
    with pytest.raises(Exception):
        asyncio.run(env.engine.run_task_by_uuid(task.uuid))
    asyncio.run(env.engine.reload())
    assert env.engine.get_task_by_uuid(task.uuid).state == scheduler.TaskState.ERROR


def test_scheduler_stop_commits_cancel_before_killing_task(env):
    task = add(env)
    run = submitted(env, task)
    deferred = env.engine._running_deferred_tasks[task.uuid]
    checked = []

    def kill(**kwargs):
        checked.append(env.owner.store.get_run(run["run_id"])["status"])

    deferred.kill = kill
    assert env.engine.cancel_running_task(task.uuid)
    assert checked == ["cancelled"]


def test_stop_before_prepare_consumes_only_the_admitted_planned_occurrence(env):
    task = add(env, "planned")
    run = submitted(env, task)
    env.owner.store.control(env.context.id, "cancel")
    asyncio.run(adapter.halted(env.owner, env.context, run, "cancelled"))
    asyncio.run(adapter.halted(env.owner, env.context, run, "cancelled"))
    asyncio.run(env.engine.reload())
    current = env.engine.get_task_by_uuid(task.uuid)
    assert current.state == scheduler.TaskState.IDLE
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1


def test_scheduler_can_stop_a_restored_held_owner_without_memory_registry(env):
    task = add(env, "planned")
    run = submitted(env, task)
    asyncio.run(adapter.prepare(env.owner, env.context, run))
    env.engine._running_deferred_tasks.clear()
    env.context.task = None
    assert env.engine.cancel_running_task(task.uuid)
    assert env.owner.store.get_run(run["run_id"])["status"] == "cancelled"
    asyncio.run(env.engine.reload())
    current = env.engine.get_task_by_uuid(task.uuid)
    assert current.state == scheduler.TaskState.IDLE
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1


def test_late_completion_callback_cannot_unregister_newer_occurrence(env):
    task = add(env)
    submitted(env, task)
    old = env.engine._running_deferred_tasks[task.uuid]
    new = Deferred()
    env.engine._register_running_task(task.uuid, new)
    old.callback(None)
    assert env.engine._running_deferred_tasks[task.uuid] is new


def test_atomic_scheduler_projection_keeps_previous_file_on_publish_failure(env, monkeypatch):
    task = add(env)
    path = Path(scheduler._task_file_path())
    original = path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(scheduler.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        asyncio.run(env.engine.update_task(task.uuid, name="Changed"))
    assert path.read_bytes() == original
    assert not list(path.parent.glob(".tasks-*"))
    assert json.loads(original)["tasks"][0]["name"] == "Work"


def test_scheduler_projection_rejects_symlink_ancestor(env):
    target = env.root / "target"
    target.mkdir()
    link = env.root / "linked"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        scheduler._write_task_projection(str(link / "tasks.json"), "private")
    assert not (target / "tasks.json").exists()


def test_durable_scheduler_cancel_does_not_terminate_unrelated_context_loop(env):
    task = add(env)
    run = submitted(env, task)
    first_started, other_started = threading.Event(), threading.Event()
    async def parked(started):
        started.set()
        await asyncio.Event().wait()
    first = env.context.run_task(parked, first_started)
    other_context = AgentContext(env.context.config, id="unrelated-live-context")
    other = other_context.run_task(parked, other_started)
    first._durable_scheduler_context_id = env.context.id
    first._durable_scheduler_input_id = run["input_id"]
    env.engine._register_running_task(task.uuid, first)
    try:
        assert first_started.wait(2) and other_started.wait(2)
        assert first.event_loop_thread is other.event_loop_thread
        assert env.engine.cancel_running_task(task.uuid, terminate_thread=True)
        assert env.owner.store.get_run(run["run_id"])["status"] == "cancelled"
        assert other.is_alive()
        assert other.event_loop_thread.loop.is_running()
    finally:
        first.kill(); other.kill()


def test_legacy_scheduler_cancel_preserves_explicit_thread_termination(env):
    task = add(env)
    flags = []
    deferred = Deferred()
    deferred.kill = lambda **kwargs: flags.append(kwargs["terminate_thread"])
    env.engine._register_running_task(task.uuid, deferred)
    assert env.engine.cancel_running_task(task.uuid, terminate_thread=True)
    assert flags == [True]


def test_cancel_from_async_api_consumes_unprepared_plan_occurrence(env):
    task = add(env, "planned")
    run = submitted(env, task)
    async def api_call():
        assert env.engine.cancel_running_task(task.uuid)
    asyncio.run(api_call())
    asyncio.run(env.engine.reload())
    current = env.engine.get_task_by_uuid(task.uuid)
    assert current.durable_status == "cancelled"
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1
    assert env.owner.store.get_run(run["run_id"])["status"] == "cancelled"


@pytest.mark.parametrize("same_input", [False, True])
def test_old_future_completion_cannot_unregister_reused_deferred_handle(env, same_input):
    task = add(env)
    old_started, new_started, release_old, callbacks_done = (threading.Event() for _ in range(4))
    async def old_work():
        old_started.set()
        while not release_old.is_set():
            await asyncio.sleep(0.005)
    async def new_work():
        new_started.set()
        await asyncio.Event().wait()
    deferred = env.context.run_task(old_work)
    old_future = deferred._future
    try:
        assert old_started.wait(2)
        adapter._register_occurrence(env.engine, task.uuid, deferred, env.context.id, "old-input")
        old_future.add_done_callback(lambda _future: callbacks_done.set())
        assert env.context.run_task(new_work) is deferred
        assert new_started.wait(2)
        adapter._register_occurrence(env.engine, task.uuid, deferred, env.context.id,
                                     "old-input" if same_input else "new-input")
        release_old.set()
        old_future.result(timeout=2)
        assert callbacks_done.wait(2)
        assert env.engine._running_deferred_tasks[task.uuid] is deferred
        assert deferred.is_alive()
    finally:
        old_future.cancel(); deferred.kill()


from test_durable_runtime import rig


def test_operator_retry_reopens_attention_occurrence_without_advancing_plan_twice(rig, monkeypatch):
    from agent import Agent
    from helpers.durable import review
    from helpers.llm_result import LLMResult
    monkeypatch.setattr(scheduler, "SCHEDULER_FOLDER", str(rig.path / "scheduler"))
    monkeypatch.setattr(scheduler.TaskScheduler, "_instance", None)
    monkeypatch.setattr(scheduler.SchedulerTaskList, "_SchedulerTaskList__instance", None)
    monkeypatch.setattr(scheduler, "initialize_agent", lambda: rig.context.config)
    monkeypatch.setattr(scheduler, "save_tmp_chat", lambda context: None)
    now = datetime(2026, 10, 22, 10, 0, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler, "_now", lambda: now)
    calls = []
    class Model:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions"}
        async def unified_turn(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("Synthetic lost outcome")
            return LLMResult.from_chat(response=json.dumps({"tool_name": "response", "tool_args": {"text": "Done"}}))
    monkeypatch.setattr(Agent, "get_chat_model", lambda self: Model())
    engine = scheduler.TaskScheduler.get()
    task = add(SimpleNamespace(engine=engine, context=rig.context, now=now), "planned")
    asyncio.run(engine._run_task(task, occurrence_id=adapter.scheduled_occurrence(task)))
    with pytest.raises(RuntimeError, match="Synthetic lost outcome"):
        rig.context.task.result_sync(timeout=10)
    run, = rig.owner.sync("list_runs")
    assert run["status"] == "attention"
    asyncio.run(engine.reload())
    current = engine.get_task_by_uuid(task.uuid)
    assert current.durable_status == "attention"
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1
    review.resolve(rig.owner, rig.context.id, run["run_id"],
                   rig.owner.sync("get_review", run["run_id"])["version"],
                   "new_attempt", "Verified synthetic outcome", "retry-scheduler-occurrence", "model:0")
    assert rig.context.task.result_sync(timeout=10) == "Done"
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "completed"
    asyncio.run(engine.reload())
    current = engine.get_task_by_uuid(task.uuid)
    assert current.durable_status == "completed" and current.state == scheduler.TaskState.IDLE
    assert len(current.plan.done) == 1 and len(current.plan.todo) == 1
    assert len(calls) == 2 and Agent.prepare_prompt.await_count == 1
