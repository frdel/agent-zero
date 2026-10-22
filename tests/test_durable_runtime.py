"""Local chat recovery against real framework history, tools and SQLite."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from agent import Agent, AgentConfig, AgentContext, LoopData, UserMessage
from helpers import extension, persist_chat, responses_history
from helpers.durable import codec, runtime
from helpers.llm_result import LLMResult
from helpers.tool import Tool, Response
from tools.response import ResponseTool


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(extension, "_get_extension_classes", lambda *args, **kwargs: [])
    monkeypatch.setattr(AgentContext, "_contexts", {})
    monkeypatch.setattr(persist_chat, "CHATS_FOLDER", str(tmp_path / "chats"))
    monkeypatch.setattr(persist_chat, "initialize_agent", lambda **kwargs: AgentConfig(mcp_servers=""))
    monkeypatch.setattr(responses_history, "prepare_call", lambda *args: {})
    monkeypatch.setattr("helpers.state_monitor_integration.mark_dirty_all", lambda **kwargs: None)
    monkeypatch.setattr("helpers.state_monitor_integration.mark_dirty_for_context", lambda *args, **kwargs: None)
    mask = SimpleNamespace(mask_values=lambda value: value.replace("sentinel-secret", "[MASKED]"))
    monkeypatch.setattr("helpers.secrets.get_secrets_manager", lambda context: mask)
    monkeypatch.setattr("helpers.log.get_secrets_manager", lambda context: mask)
    owner = runtime.RecoveryService((tmp_path / "durable").resolve())
    monkeypatch.setattr(runtime, "_service", owner)
    requested = []

    class Model:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions", "api_key": "sentinel-secret"}

        async def unified_turn(self, **kwargs):
            requested.append(kwargs)
            return LLMResult.from_chat(response=json.dumps({"tool_name": "response", "tool_args": {"text": "Done"}}))

    monkeypatch.setattr(Agent, "get_chat_model", lambda self: Model())
    monkeypatch.setattr(Agent, "prepare_prompt", AsyncMock(return_value=[HumanMessage(content="Synthetic input")]))
    monkeypatch.setattr("helpers.mcp_handler.MCPConfig.get_instance", lambda: SimpleNamespace(get_tool=lambda *args: None))
    monkeypatch.setattr(Agent, "parse_prompt", lambda self, name, **kwargs: kwargs.get("message", ""))
    monkeypatch.setattr(Agent, "read_prompt", lambda *args, **kwargs: "Synthetic prompt")

    def resolve(self, name, method, args, message, loop_data):
        return ResponseTool(self, name, method, args, message, loop_data)

    monkeypatch.setattr(Agent, "get_tool", resolve)
    context = AgentContext(AgentConfig(mcp_servers=""), id="synthetic-context")
    yield SimpleNamespace(owner=owner, context=context, requests=requested, path=tmp_path)
    for ctx in AgentContext.all():
        if ctx.task:
            ctx.task.kill()
    owner.close()


def test_opt_in_chat_completes_through_real_model_and_response_boundaries(rig):
    task = rig.context.communicate(UserMessage("Hello", id="input-1"))
    assert task.result_sync(timeout=10) == "Done"
    assert len(rig.requests) == 1
    run, = rig.owner.sync("list_runs")
    assert run["status"] == "completed"
    assert [message.ai for message in rig.context.agent0.history.all_messages()] == [False, True]
    assert rig.owner.sync("get_call", run["run_id"], "model:0")["status"] == "completed"
    assert rig.context.communicate(UserMessage("Hello", id="input-1")).result_sync(timeout=5) == "Done"
    assert len(rig.requests) == 1


def admitted(rig, phase, result=None):
    agent = rig.context.agent0
    agent.hist_add_user_message(UserMessage("Hello", id="input-1"))
    agent.loop_data = LoopData(iteration=0, user_message=agent.last_user_message)
    payload = codec.message_payload(UserMessage("Hello", id="input-1"))
    run = rig.owner.sync("admit", rig.context.id, "input-1", payload, codec.checkpoint(agent, result=result))
    return rig.owner.sync("transition", run["run_id"], phase, checkpoint=codec.checkpoint(agent, result=result))


@pytest.mark.parametrize("mode", ["chat_completions", "responses"])
def test_committed_model_result_recovers_without_another_model_call(rig, mode):
    result = LLMResult.from_chat(response=json.dumps({"tool_name": "response", "tool_args": {"text": "Recovered"}}))
    result.mode = mode
    run = admitted(rig, "model_result", result)
    rig.owner.recover()
    restored = AgentContext.get(rig.context.id)
    assert restored.task.result_sync(timeout=10) == "Recovered"
    assert rig.requests == []
    messages = restored.agent0.history.all_messages()
    assert len(messages) == 2 and messages[1].ai
    assert next(item for item in restored.log.logs if item.type == "response").content == "Recovered"
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "completed"


@pytest.mark.parametrize("phase", ["model_inflight", "processing_model", "finalizing", "terminal_ready", "preparing"])
def test_uncertain_phase_is_held_without_new_effects(rig, phase):
    run = admitted(rig, phase)
    rig.owner.recover()
    restored = AgentContext.get(rig.context.id)
    assert "not retried" in restored.task.result_sync(timeout=10)
    assert rig.requests == []
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "attention"


def test_raw_model_codec_masks_credentials_and_excludes_sdk_raw(rig):
    result = LLMResult.from_chat(response="sentinel-secret")
    result.raw = {"api_key": "sentinel-secret"}
    result.capability = {"fallback_error": "unregistered-token", "mode": "chat_completions"}
    result.output_items = []
    data = codec.result_payload(rig.context.agent0, result)
    assert "raw" not in data
    assert "sentinel-secret" not in json.dumps(data)
    assert "unregistered-token" not in json.dumps(data)
    assert "api_key" not in json.dumps(codec.environment(rig.context.agent0))


def test_tool_body_result_survives_intervention_check_failure(rig, monkeypatch):
    from helpers.tool_execution import execute_tool
    from helpers.durable.runtime import RecoveryHeld, Turn
    run = admitted(rig, "tools")
    agent = rig.context.agent0
    agent.context._durable_turn = turn = Turn(rig.owner, agent, run)
    turn.recovered = False  # Exercise a fresh body's interruption, then replay its record.
    hits = []

    class Effect(Tool):
        async def execute(self, **kwargs):
            hits.append("effect")
            return Response("Performed", False)

    tool = Effect(agent, "effect", None, {}, "", agent.loop_data)
    checks = 0

    async def check(*args):
        nonlocal checks
        checks += 1
        if checks == 3:
            raise RecoveryHeld("interrupted_after_body")

    monkeypatch.setattr(agent, "handle_intervention", check)
    with pytest.raises(RecoveryHeld):
        asyncio.run(execute_tool(tool, {}))
    body = rig.owner.sync("get_call", run["run_id"], "tool:0:0")
    assert hits == ["effect"] and body["result"]["response"]["message"] == "Performed"
    turn.tool_index = 0
    with pytest.raises(RecoveryHeld, match="tool_finalization_interrupted"):
        asyncio.run(execute_tool(tool, {}))
    assert hits == ["effect"]


def test_finalized_native_call_is_not_repeated_and_preserves_call_id(rig):
    result = LLMResult.from_response({"id": "response-a", "output": [{
        "type": "function_call", "name": "response", "call_id": "native-call", "arguments": '{"text":"Done"}'}]})
    run = admitted(rig, "model_ready", result)
    rig.owner.recover()
    ctx = AgentContext.get(rig.context.id)
    assert ctx.task.result_sync(timeout=10) == "Done"
    final = rig.owner.sync("get_call", run["run_id"], "tool:0:0:final")
    item = final["result"]["response"]["additional"]["_responses_output_item"]
    assert item["call_id"] == "native-call"
    assert rig.requests == []


def test_stop_and_reset_fence_old_work(rig):
    run = admitted(rig, "iteration_ready")
    rig.context.kill_process()
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "cancelled"
    rig.owner.recover()
    assert rig.requests == []
    rig.context.reset()
    task = rig.context.communicate(UserMessage("New", id="input-2"))
    assert task.result_sync(timeout=10) == "Done"


def test_disabled_backend_does_not_resume_or_bypass_held_work(rig):
    admitted(rig, "iteration_ready")
    rig.owner.enabled = False
    rig.owner.recover()
    with pytest.raises(RuntimeError, match="held durable run"):
        rig.context.communicate(UserMessage("New", id="input-2"))
    assert rig.requests == []


def test_configuration_drift_holds_before_provider_request(rig, monkeypatch):
    run = admitted(rig, "iteration_ready")
    monkeypatch.setattr(Agent, "get_chat_model", lambda self: SimpleNamespace(model_name="changed", kwargs={}))
    rig.owner.recover()
    ctx = AgentContext.get(rig.context.id)
    if ctx.task:
        with pytest.raises(ValueError):
            ctx.task.result_sync(timeout=10)
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "attention"
    assert rig.requests == []


def test_old_input_retry_does_not_replace_active_task_handle(rig):
    assert rig.context.communicate(UserMessage("Hello", id="input-1")).result_sync(timeout=10) == "Done"
    run = rig.owner.sync(
        "admit", rig.context.id, "input-2", {"message": "Other"}, codec.checkpoint(rig.context.agent0))
    marker = SimpleNamespace(kill=lambda: None)
    rig.context.task = marker
    rig.owner.driving.add(run["run_id"])
    report = rig.context.communicate(UserMessage("Hello", id="input-1"))
    assert report.result_sync(timeout=5) == "Done"
    assert rig.context.task is marker
    rig.context.task = None
    rig.owner.driving.discard(run["run_id"])


def test_new_admission_waits_for_cancelled_runner_cleanup(rig):
    run = admitted(rig, "iteration_ready")
    rig.owner.driving.add(run["run_id"])
    rig.context.kill_process()
    with pytest.raises(RuntimeError, match="still stopping"):
        rig.context.communicate(UserMessage("New", id="input-2"))
    assert rig.requests == []
    rig.owner.driving.discard(run["run_id"])


def test_unknown_plugin_state_is_not_serialized_and_requires_adapter(rig):
    rig.context.data["plugin_state"] = {"Authorization": "Bearer unregistered-token"}
    projection = codec.checkpoint(rig.context.agent0)
    assert "unregistered-token" not in json.dumps(projection)
    assert projection["requires_state_adapter"] is True
    with pytest.raises(ValueError, match="plugin state adapter"):
        codec.restore(rig.context, projection)


def test_intervention_is_durable_and_second_pending_message_is_rejected(rig, monkeypatch):
    import threading
    started = threading.Event()
    release = threading.Event()

    class WaitingModel:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions", "api_key": "sentinel-secret"}

        async def unified_turn(self, **kwargs):
            started.set()
            await asyncio.to_thread(release.wait)
            return LLMResult.from_chat(response='{"tool_name":"response","tool_args":{"text":"Done"}}')

    monkeypatch.setattr(Agent, "get_chat_model", lambda self: WaitingModel())
    task = rig.context.communicate(UserMessage("Hello", id="input-1"))
    try:
        assert started.wait(5)
        assert rig.context.communicate(UserMessage("Change course", id="input-2")) is task
        assert rig.context.communicate(UserMessage("Change course", id="input-2")) is task
        with pytest.raises(RuntimeError, match="already pending"):
            rig.context.communicate(UserMessage("Another message", id="input-3"))
        run, = rig.owner.sync("list_runs")
        assert run["checkpoint"]["intervention"]["id"] == "input-2"
    finally:
        release.set()
    assert "not retried" in task.result_sync(timeout=10)
    run, = rig.owner.sync("list_runs")
    assert run["status"] == "attention"
    assert run["checkpoint"]["last_user_message_id"] == "input-2"


def test_backup_is_held_on_restore(rig):
    admitted(rig, "iteration_ready")
    backup = rig.owner.sync("backup", (rig.path / "copy.sqlite3"))
    restored_root = rig.path / "restored"
    restored_root.mkdir()
    import shutil
    shutil.copyfile(backup, restored_root / "state.sqlite3")
    restored = runtime.RecoveryService(restored_root)
    try:
        restored.recover()
        assert rig.requests == []
        assert AgentContext.get(rig.context.id).task is None
    finally:
        restored.close()


def test_corrupt_checkpoint_does_not_prevent_other_context_recovery(rig):
    bad = admitted(rig, "iteration_ready")
    other = AgentContext(AgentConfig(mcp_servers=""), id="other-context")
    payload = codec.message_payload(UserMessage("Hello", id="other-input"))
    rig.owner.sync("admit", other.id, "other-input", payload, codec.checkpoint(other.agent0))
    # Fault injection is confined to this fixture's private database.
    import sqlite3
    with sqlite3.connect(rig.path / "durable" / "state.sqlite3") as connection:
        connection.execute("UPDATE runs SET checkpoint='{}' WHERE run_id=?", (bad["run_id"],))
    # Corrupt candidate is isolated; a healthy, unrelated candidate still runs.
    rig.owner.recover()
    assert len(rig.owner.sync("list_run_headers")) == 2
    assert AgentContext.get(other.id).task.result_sync(timeout=10) == "Done"


def test_shared_model_stage_preserves_stream_callbacks_and_prepares_once(rig, monkeypatch):
    calls = []
    class StreamingModel:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions"}
        async def unified_turn(self, **kwargs):
            await kwargs["reasoning_callback"]("Plan", "Plan")
            text = '{"tool_name":"response","tool_args":{"text":"Done"}}'
            calls.append(await kwargs["response_callback"](text, text))
            return LLMResult.from_chat(response=text)
    monkeypatch.setattr(Agent, "get_chat_model", lambda self: StreamingModel())
    assert rig.context.communicate(UserMessage("Hello", id="stream-input")).result_sync(timeout=10) == "Done"
    assert json.loads(calls[0])["tool_name"] == "response"
    assert Agent.prepare_prompt.await_count == 1


def test_cancellation_during_initial_read_releases_runner_reservation(rig, monkeypatch):
    run = admitted(rig, "iteration_ready")
    original = rig.owner.io

    async def exercise():
        entered = asyncio.Event()
        async def delayed(method, *args, **kwargs):
            if method == "get_run":
                entered.set()
                await asyncio.Future()
            return await original(method, *args, **kwargs)
        monkeypatch.setattr(rig.owner, "io", delayed)
        rig.owner.driving.add(run["run_id"])
        task = asyncio.create_task(rig.owner.run(rig.context, run))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    assert run["run_id"] not in rig.owner.driving
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "cancelled"
    assert rig.requests == []


@pytest.mark.parametrize("gate", ["disabled", "backup"])
def test_unpause_cannot_bypass_recovery_hold(rig, monkeypatch, gate):
    run = admitted(rig, "iteration_ready")
    runtime.pause_context(rig.context, True)
    if gate == "disabled":
        rig.owner.enabled = False
    else:
        original = rig.owner.sync
        monkeypatch.setattr(rig.owner, "sync", lambda method, *a, **kw:
                            False if method == "can_resume" else original(method, *a, **kw))
    with pytest.raises(RuntimeError, match="unpause is unavailable"):
        runtime.pause_context(rig.context, False)
    assert rig.context.paused
    held = rig.owner.sync("get_run", run["run_id"])
    assert held["status"] == "blocked" and held["checkpoint"]["paused"]
    assert rig.requests == [] and not rig.owner.driving


def test_stopped_intervention_retry_never_becomes_a_new_run(rig):
    run = admitted(rig, "iteration_ready")
    message = UserMessage("Change course", id="intervention-id")
    import hashlib
    call_id = "input:" + hashlib.sha256(message.id.encode()).hexdigest()
    rig.owner.sync("start_call", run["run_id"], call_id, "intervention", codec.message_payload(message))
    rig.owner.sync("finish_call", run["run_id"], call_id, {"accepted": True})
    rig.context.kill_process()
    report = rig.context.communicate(message)
    assert "already recorded" in report.result_sync(timeout=5)
    assert len(rig.owner.sync("list_run_headers")) == 1
    with pytest.raises(ValueError, match="different content"):
        rig.context.communicate(UserMessage("Changed", id="intervention-id"))
    assert rig.requests == []


def test_retained_input_fingerprint_deduplicates_after_payload_expiry(rig):
    assert rig.context.communicate(UserMessage("Hello", id="input-1")).result_sync(timeout=10) == "Done"
    result = rig.owner.sync("compact", retain_terminal=0, max_age_days=0)
    assert result["runs_pruned"] == 1
    assert "payload has expired" in rig.context.communicate(UserMessage("Hello", id="input-1")).result_sync(timeout=5)
    with pytest.raises(ValueError, match="different content"):
        rig.context.communicate(UserMessage("Different", id="input-1"))
    assert len(rig.requests) == 1


def scheduler_engine(rig, monkeypatch):
    from helpers import task_scheduler as scheduled
    monkeypatch.setattr(scheduled, "SCHEDULER_FOLDER", str(rig.path / "scheduler"))
    monkeypatch.setattr(scheduled.TaskScheduler, "_instance", None)
    monkeypatch.setattr(scheduled.SchedulerTaskList, "_SchedulerTaskList__instance", None)
    monkeypatch.setattr(scheduled, "save_tmp_chat", lambda context: None)
    return scheduled.TaskScheduler.get()


def test_scheduler_admission_runs_real_coordinator_and_projects_one_result(rig, monkeypatch):
    from helpers import task_scheduler as scheduled
    engine = scheduler_engine(rig, monkeypatch)
    task = scheduled.AdHocTask(name="Synthetic", system_prompt="", prompt="Work", context_id=rig.context.id)
    asyncio.run(engine._tasks.add_task(task))
    asyncio.run(engine._run_task(task))
    assert rig.context.task.result_sync(timeout=10) == "Done"
    asyncio.run(engine.reload())
    projected = engine.get_task_by_uuid(task.uuid)
    assert projected.state == scheduled.TaskState.IDLE
    assert projected.last_result == "Done" and projected.durable_status == "completed"
    run, = rig.owner.sync("list_runs")
    assert run["status"] == "completed"
    assert run["checkpoint"]["context"]["data"]["scheduler_task_uuid"] == task.uuid
    assert len(rig.requests) == 1


def test_scheduler_projection_commit_before_run_completion_recovers_without_inference(rig, monkeypatch):
    from helpers import task_scheduler as scheduled
    from helpers.durable import scheduler as adapter
    engine = scheduler_engine(rig, monkeypatch)
    task = scheduled.AdHocTask(name="Synthetic", system_prompt="", prompt="Work", context_id=rig.context.id)
    asyncio.run(engine._tasks.add_task(task))
    # Stop at admission: reconstruct the durable phase reached after a successful
    # monologue and scheduler projection, before the outer completed commit.
    from helpers.defer import DeferredTask
    dispatch = rig.owner.dispatch
    monkeypatch.setattr(rig.owner, "dispatch", lambda context, run: DeferredTask("SyntheticReport").start_task(
        rig.owner._reported_result, run))
    asyncio.run(engine._run_task(task))
    run, = rig.owner.sync("list_runs")
    asyncio.run(adapter.prepare(rig.owner, rig.context, run))
    rig.context.agent0.loop_data = LoopData()
    data = codec.checkpoint(rig.context.agent0, terminal="Already finished")
    run = rig.owner.sync("transition", run["run_id"], "scheduler_finalizing", checkpoint=data)
    asyncio.run(adapter.complete(rig.owner, rig.context, run, "Already finished"))
    monkeypatch.setattr(rig.owner, "dispatch", dispatch)
    rig.owner.recover()
    restored = AgentContext.get(rig.context.id)
    assert restored.task.result_sync(timeout=10) == "Already finished"
    assert rig.requests == []
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "completed"
    asyncio.run(engine.reload())
    assert engine.get_task_by_uuid(task.uuid).last_result == "Already finished"


def test_cancel_winning_model_projection_preserves_known_late_outcome(rig, monkeypatch):
    original = rig.owner.io
    cancelled = False
    async def cancel_before_projection(method, *args, **kwargs):
        nonlocal cancelled
        if method == "finish_call" and args[1] == "model:0" and not cancelled:
            cancelled = True
            rig.owner.sync("control", rig.context.id, "cancel")
        return await original(method, *args, **kwargs)
    monkeypatch.setattr(rig.owner, "io", cancel_before_projection)
    assert rig.context.communicate(UserMessage("Hello", id="cancel-race")).result_sync(timeout=10) == "Stopped"
    run, = rig.owner.sync("list_runs")
    result = rig.owner.sync("get_call", run["run_id"], "model:0")
    assert run["status"] == "cancelled" and result["status"] == "completed"
    assert "Done" in result["result"]["response"]
    assert len(rig.requests) == 1


def test_parent_delete_fences_descendants_and_removes_owned_snapshots(rig, monkeypatch):
    parent = admitted(rig, "iteration_ready")
    child = AgentContext(AgentConfig(mcp_servers=""), id="owned-child")
    origin = {"kind": "child", "mode": "subordinate", "parent_run_id": parent["run_id"],
              "parent_context_id": rig.context.id, "parent_agent_number": 0,
              "parent_call_id": "tool:0:0", "index": 0}
    child._durable_origin = origin
    run = rig.owner.sync("admit", child.id, "child-input", {}, codec.checkpoint(child.agent0))
    rig.owner.sync("start_call", run["run_id"], "unknown-effect", "tool", {})
    for context in (rig.context, child):
        folder = Path(persist_chat.get_chat_folder_path(context.id))
        folder.mkdir(parents=True)
        (folder / "chat.json").write_text("synthetic private snapshot")
    cleaned = []
    monkeypatch.setattr(persist_chat, "_delete_provider_responses_for_chat", cleaned.append)
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == [rig.context.id, child.id]
    assert AgentContext.get(child.id) is None
    for context in (rig.context, child):
        assert not Path(persist_chat.get_chat_folder_path(context.id)).exists()
        header, = rig.owner.sync("list_run_headers", context_id=context.id)
        assert header["status"] == "cancelled"
        assert rig.owner.sync("get_run", header["run_id"])["checkpoint"] is None
    from helpers.durable.store import StaleRunError
    with pytest.raises(StaleRunError):
        rig.owner.sync("finish_call", run["run_id"], "unknown-effect", {"late": True})


def test_parallel_children_share_bounded_execution_and_release_worker_contexts(rig, monkeypatch):
    from helpers import parallel_tools
    from tools.parallel import ParallelTool
    active = maximum = 0
    effects = []

    class Effect(Tool):
        async def execute(self, value="", **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            effects.append(value)
            try:
                await asyncio.sleep(.02)
                return Response(value, False)
            finally:
                active -= 1

    class BatchModel:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions"}
        async def unified_turn(self, **kwargs):
            rig.requests.append(kwargs)
            calls = {"tool_calls": [{"tool_name": "effect", "tool_args": {"value": str(index)}} for index in range(5)]}
            return LLMResult.from_response({"id": "batch-response", "output": [
                {"type": "function_call", "name": "parallel", "call_id": "batch-call", "arguments": json.dumps(calls)},
                {"type": "function_call", "name": "response", "call_id": "answer-call", "arguments": '{"text":"Done"}'},
            ]})
    def resolve(agent, name, method, args, message, loop_data):
        cls = ParallelTool if name == "parallel" else ResponseTool if name == "response" else Effect
        return cls(agent, name, method, args, message, loop_data)
    monkeypatch.setattr(Agent, "get_chat_model", lambda self: BatchModel())
    monkeypatch.setattr(Agent, "get_tool", resolve)
    monkeypatch.setattr(parallel_tools, "_resolve_parallel_tool", lambda agent, name, args, **kw:
                        resolve(agent, name, None, args, "", agent.loop_data))
    assert rig.context.communicate(UserMessage("Batch", id="batch-input")).result_sync(timeout=10) == "Done"
    assert sorted(effects) == ["0", "1", "2", "3", "4"] and maximum == 2
    assert AgentContext.all() == [rig.context]
    assert not rig.owner.executing and not rig.owner.waiting


def test_nested_active_child_protects_all_ancestor_recovery_payloads(rig):
    from helpers.durable.workflows import protected_run_ids
    root = admitted(rig, "iteration_ready")
    rig.owner.sync("transition", root["run_id"], "completed", status="completed")
    parent = root
    runs = [root]
    for index in range(2):
        context = AgentContext(AgentConfig(mcp_servers=""), id=f"nested-{index}")
        context._durable_origin = {"kind": "child", "mode": "subordinate", "parent_run_id": parent["run_id"],
                                  "parent_context_id": parent["context_id"], "parent_agent_number": index,
                                  "parent_call_id": "tool:0:0", "index": 0}
        run = rig.owner.sync("admit", context.id, f"child-{index}", {}, codec.checkpoint(context.agent0))
        if index == 0:
            run = rig.owner.sync("transition", run["run_id"], "completed", status="completed")
        runs.append(run)
        parent = run
    protected = protected_run_ids(rig.owner)
    assert {run["run_id"] for run in runs} <= protected
    assert rig.owner.sync("compact", retain_terminal=0, max_age_days=0, protected_run_ids=protected)["runs_pruned"] == 0


def test_paused_parent_delays_admitted_child_without_marking_it_uncertain(rig, monkeypatch):
    import threading
    from helpers import parallel_tools
    parent = admitted(rig, "iteration_ready")
    runtime.pause_context(rig.context, True)
    context = AgentContext(AgentConfig(mcp_servers=""), id="paused-child")
    origin = {"kind": "child", "mode": "tool", "tool_name": "effect", "tool_args": {},
              "parent_run_id": parent["run_id"], "parent_context_id": rig.context.id,
              "parent_agent_number": 0, "parent_call_id": "tool:0:0", "index": 0, "job_id": "paused-job"}
    observed, executed = threading.Event(), threading.Event()
    original = rig.owner.io
    async def observe(method, *args, **kwargs):
        result = await original(method, *args, **kwargs)
        if method == "get_run" and args[0] == parent["run_id"] and result["status"] == "blocked":
            observed.set()
        return result
    class Effect(Tool):
        async def execute(self, **kwargs):
            executed.set()
            return Response("Worked", False)
    monkeypatch.setattr(rig.owner, "io", observe)
    monkeypatch.setattr(parallel_tools, "_resolve_parallel_tool", lambda agent, name, args, **kw:
                        Effect(agent, name, None, args, "", agent.loop_data))
    task = rig.owner.submit_owned(context, UserMessage("Child", id="paused-child-input"), origin)
    assert observed.wait(5) and not executed.is_set()
    child_run, = rig.owner.sync("list_run_headers", context_id=context.id)
    assert child_run["status"] == "running"
    runtime.pause_context(rig.context, False)
    assert task.result_sync(timeout=10) == "Worked"
    assert executed.is_set()
    assert rig.context.task.result_sync(timeout=10) == "Done"


@pytest.mark.parametrize("restored", [False, True])
def test_admitted_restart_cannot_make_an_unaudited_target_fresh(rig, monkeypatch, restored):
    from tools.wait import WaitTool
    effects, provider_calls = [], []
    async def external_body(self, **kwargs):
        effects.append("effect")
        return Response("Synthetic effect", False)
    class Model:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions"}
        async def unified_turn(self, **kwargs):
            provider_calls.append(kwargs)
            request = {"tool_name": "wait", "tool_args": {"seconds": 0}} if len(provider_calls) == 1 else {
                "tool_name": "response", "tool_args": {"text": "Done"}}
            return LLMResult.from_chat(response=json.dumps(request))
    monkeypatch.setattr(WaitTool, "execute", external_body)
    monkeypatch.setattr(Agent, "get_chat_model", lambda self: Model())
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        (WaitTool if name == "wait" else ResponseTool)(self, name, method, args, message, loop_data))
    message = UserMessage("Pending admission", id="admitted-restart")
    run = rig.owner.sync("admit", rig.context.id, message.id, codec.message_payload(message), codec.checkpoint(rig.context.agent0))
    rig.context._durable_restored = restored
    task = rig.owner.dispatch(rig.context, run)
    task.result_sync(timeout=10)
    assert rig.owner.sync("get_run", run["run_id"])["status"] == ("attention" if restored else "completed")
    assert effects == ([] if restored else ["effect"])
    assert len(provider_calls) == (1 if restored else 2)
