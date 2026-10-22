"""Child manifests, stable joins and recovery ownership use the real ledger."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent import Agent, AgentContext, LoopData, UserMessage
from helpers.durable import codec, runtime, workflows
from helpers.tool import Response, Tool
from tools.parallel import ParallelTool
from tools.call_subordinate import Delegation

# The framework fixture supplies private temp storage, a synthetic model and no
# extension hooks/providers. Reuse it rather than creating a second model rig.
from test_durable_runtime import rig


def parent_turn(rig):
    agent = rig.context.agent0
    agent.loop_data = LoopData(iteration=0)
    run = rig.owner.sync("admit", rig.context.id, "parent-input", {"message": "Parent"}, codec.checkpoint(agent))
    turn = runtime.Turn(rig.owner, agent, run)
    turn.active_call_id = "tool:0:0"
    rig.context._durable_turn = turn
    return turn


def finish_child(turn, child, terminal="Child result"):
    run = turn.owner.sync("admit", child["context_id"], child["input_id"],
                          codec.message_payload(UserMessage(child["message"], attachments=child["attachments"],
                                                             id=child["input_id"])), child["genesis"])
    data = dict(child["genesis"], terminal=terminal)
    return turn.owner.sync("transition", run["run_id"], "completed", checkpoint=data, status="completed")


@pytest.mark.asyncio
async def test_manifest_is_committed_before_admission_and_reuses_contexts(rig):
    turn = parent_turn(rig)
    specs = [{"name": "synthetic_tool", "args": {"item": index}} for index in range(2)]
    children = await workflows._manifest(turn, specs)
    assert [child["index"] for child in children] == [0, 1]
    assert len({child["context_id"] for child in children}) == 2
    assert all(not rig.owner.sync("list_run_headers", context_id=child["context_id"]) for child in children)
    assert await workflows._manifest(turn, specs) == children
    assert len(AgentContext.all()) == 3
    assert children[0]["genesis"]["origin"]["parent_run_id"] == turn.run_id


@pytest.mark.asyncio
async def test_unfinished_child_creation_intent_never_creates_replacement(rig):
    turn = parent_turn(rig)
    rig.owner.sync("start_call", turn.run_id, "tool:0:0:workflow", "workflow",
                   {"specifications": [{"name": "synthetic_tool", "args": {}}]})
    with pytest.raises(runtime.RecoveryHeld, match="child_creation_interrupted"):
        await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    assert len(AgentContext.all()) == 1


@pytest.mark.asyncio
async def test_completed_child_join_reuses_result_and_preserves_history_once(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    run = finish_child(turn, child)
    # Parent history is recorded while running, before child completion.
    # Add it to a second real child below; completed ledgers reject new effects.
    task = SimpleNamespace(result=AsyncMock(return_value="Child result"))
    joined = await workflows._join(turn, child, task)
    again = await workflows._join(turn, child, task)
    assert joined == again and joined["child_run_id"] == run["run_id"]
    assert task.result.await_count == 1
    assert joined["result"] == "Child result"


@pytest.mark.asyncio
async def test_nonterminal_or_cancelled_child_cannot_be_joined_as_success(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    run = rig.owner.sync("admit", child["context_id"], child["input_id"], {}, child["genesis"])
    rig.owner.sync("transition", run["run_id"], "needs_attention", status="attention")
    with pytest.raises(runtime.RecoveryHeld, match="child_requires_attention"):
        workflows._submit(turn, child)
    task = SimpleNamespace(result=AsyncMock(return_value="Needs attention warning"))
    with pytest.raises(runtime.RecoveryHeld, match="child_requires_attention"):
        await workflows._join(turn, child, task)


@pytest.mark.asyncio
async def test_parent_history_and_collection_checkpoint_commit_once(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    context = AgentContext.get(child["context_id"])
    context.agent0.loop_data = LoopData(iteration=0)
    run = rig.owner.sync("admit", child["context_id"], child["input_id"], {}, child["genesis"])
    context._durable_turn = runtime.Turn(rig.owner, context.agent0, run)
    assert workflows.queue_parent_history(context.agent0, content="Queued content", tokens=3)
    rig.owner.sync("transition", run["run_id"], "completed", status="completed",
                   checkpoint=dict(child["genesis"], terminal="Done"))
    task = SimpleNamespace(result=AsyncMock(return_value="Done"))
    joined = await workflows._join(turn, child, task)
    tool = SimpleNamespace(agent=turn.agent, _durable_collection=[joined])
    await workflows.collect(tool)
    await workflows.collect(tool)
    messages = turn.agent.history.all_messages()
    assert len(messages) == 1 and "Queued content" in str(messages[0].content)
    record = rig.owner.sync("get_call", turn.run_id, "tool:0:0:collection")
    assert record["status"] == "completed"
    assert child["job_id"] not in workflows._inventory(turn)
    checkpoint = rig.owner.sync("get_run", turn.run_id)["checkpoint"]
    assert "Queued content" in str(checkpoint["context"]["agents"][0]["history"])


@pytest.mark.asyncio
async def test_rebuilt_worker_metadata_preserves_cleanup_handle_and_authorization(rig):
    from helpers.parallel_tools import get_parallel_worker_job
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {"value": 7}}])
    context = AgentContext.get(child["context_id"])
    assert context.get_output_data("parent_context_id") == rig.context.id
    job = get_parallel_worker_job(context.agent0)
    assert job.id == child["job_id"] and job.tool_args == {"value": 7}
    run = finish_child(turn, child)
    assert workflows.descendant_context_ids(rig.owner, turn.run_id) == [context.id]


def test_only_exact_bundled_workflow_types_are_supported():
    class CustomParallel(ParallelTool):
        pass
    assert workflows.supports(object.__new__(ParallelTool))
    assert workflows.supports(object.__new__(Delegation))
    assert not workflows.supports(object.__new__(CustomParallel))


@pytest.mark.asyncio
async def test_retention_keeps_cross_turn_collection_tombstone_while_batch_is_live(rig):
    first = parent_turn(rig)
    children = await workflows._manifest(first, [{"name": "synthetic_tool", "args": {"n": n}} for n in range(2)])
    child_runs = [finish_child(first, child) for child in children]
    rig.owner.sync("transition", first.run_id, "completed", status="completed")
    run = rig.owner.sync("admit", rig.context.id, "collector-input", {}, codec.checkpoint(first.agent))
    collector = runtime.Turn(rig.owner, first.agent, run)
    collector.active_call_id = "tool:1:0"
    rig.context._durable_turn = collector
    result = await workflows._join(collector, children[0], SimpleNamespace(result=AsyncMock(return_value="Done")))
    await workflows.collect(SimpleNamespace(agent=collector.agent, _durable_collection=[result]))
    rig.owner.sync("transition", collector.run_id, "completed", status="completed")
    protected = workflows.protected_run_ids(rig.owner)
    assert {first.run_id, collector.run_id, *(run["run_id"] for run in child_runs)} <= protected
    assert list(workflows._inventory(collector)) == [children[1]["job_id"]]


@pytest.mark.asyncio
async def test_cancel_ignores_stale_child_ownership_after_independent_turn(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    finish_child(turn, child)
    context = AgentContext.get(child["context_id"])
    context._durable_origin = None
    rig.owner.sync("admit", child["context_id"], "independent-input", {}, codec.checkpoint(context.agent0))
    assert workflows.descendant_context_ids(rig.owner, turn.run_id) == []


def test_real_parent_parallel_child_tools_run_once_through_durable_dispatch(rig, monkeypatch):
    import json
    from helpers.llm_result import LLMResult
    from tools.response import ResponseTool
    effects, model_calls = [], []

    class ChildTool(Tool):
        async def execute(self, **kwargs):
            effects.append(kwargs["value"])
            return Response(f"Child {kwargs['value']}", False)

    calls = {"tool_calls": [{"tool_name": "synthetic_tool", "tool_args": {"value": index}} for index in range(2)]}

    class Model:
        model_name = "synthetic"
        kwargs = {"a0_api_mode": "chat_completions"}
        async def unified_turn(self, **kwargs):
            model_calls.append(kwargs)
            if len(model_calls) == 1:
                return LLMResult.from_chat(response=json.dumps({"tool_name": "parallel", "tool_args": calls}))
            return LLMResult.from_chat(response=json.dumps({"tool_name": "response", "tool_args": {"text": "Parent done"}}))

    monkeypatch.setattr(Agent, "get_chat_model", lambda self: Model())
    classes = {"parallel": ParallelTool, "synthetic_tool": ChildTool, "response": ResponseTool}
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        classes[name](self, name, method, args, message, loop_data))
    task = rig.context.communicate(UserMessage("Run children", id="parent-workflow"))
    assert task.result_sync(timeout=10) == "Parent done"
    assert sorted(effects) == [0, 1]
    assert len(model_calls) == 2  # direct children never call a provider
    parent = next(run for run in rig.owner.sync("list_runs") if run["context_id"] == rig.context.id)
    joins = [call for call in rig.owner.sync("calls", parent["run_id"]) if call["kind"] == "child_join"]
    assert len(joins) == 2 and all(call["status"] == "completed" for call in joins)
    assert [call["result"]["result"] for call in joins] == ["Child 0", "Child 1"]
    assert rig.context.communicate(UserMessage("Run children", id="parent-workflow")).result_sync(timeout=5) == "Parent done"
    assert sorted(effects) == [0, 1]


@pytest.mark.asyncio
async def test_recovered_parallel_wrapper_reuses_completed_child_without_effect(rig, monkeypatch):
    import json
    from helpers.durable import replay
    from helpers.llm_result import LLMResult
    from tools.response import ResponseTool
    turn = parent_turn(rig)
    args = {"tool_calls": [{"tool_name": "synthetic_tool", "tool_args": {"value": 1}}]}
    turn.result = LLMResult.from_chat(response=json.dumps({"tool_name": "parallel", "tool_args": args}))
    await turn.save("tools")
    tool = ParallelTool(turn.agent, "parallel", None, args, "", turn.agent.loop_data)
    monkeypatch.setattr(replay, "AUDITED_WORKFLOWS", {(type(tool).__name__, codec.identity(tool)["source"])})
    await turn.tool_begin(tool, args)
    await turn.effective_tool_args(turn.active_call_id, args)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {"value": 1}}])
    finish_child(turn, child, terminal="Recorded child output")
    effects = []

    class ForbiddenChild(Tool):
        async def execute(self, **kwargs):
            effects.append(True)
            raise AssertionError("Completed child must not execute")

    classes = {"parallel": ParallelTool, "synthetic_tool": ForbiddenChild, "response": ResponseTool}
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        classes[name](self, name, method, args, message, loop_data))
    rig.context._durable_turn = None
    rig.owner.recover()
    restored = AgentContext.get(rig.context.id)
    result = await asyncio.to_thread(restored.task.result_sync, timeout=10)
    assert result == "Done"
    assert effects == []
    assert len(rig.requests) == 1  # only the parent's next turn, no repeated batch
    calls = rig.owner.sync("calls", turn.run_id)
    join, = [call for call in calls if call["kind"] == "child_join"]
    assert join["result"]["result"] == "Recorded child output"


@pytest.mark.asyncio
async def test_stop_finds_descendants_even_when_owned_child_checkpoint_is_corrupt(rig, monkeypatch):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    context = AgentContext.get(child["context_id"])
    run = rig.owner.sync("admit", child["context_id"], child["input_id"], {}, child["genesis"])
    child_turn = runtime.Turn(rig.owner, context.agent0, run)
    context.agent0.loop_data = LoopData(iteration=0)
    child_turn.active_call_id = "tool:0:0"
    context._durable_turn = child_turn
    grandchild, = await workflows._manifest(child_turn, [{"name": "synthetic_tool", "args": {}}])
    rig.owner.sync("admit", grandchild["context_id"], grandchild["input_id"], {}, grandchild["genesis"])
    original = rig.owner.sync
    def read(method, *args, **kwargs):
        if method == "get_run" and args[0] == run["run_id"]:
            raise ValueError("Corrupt child checkpoint")
        return original(method, *args, **kwargs)
    monkeypatch.setattr(rig.owner, "sync", read)
    assert workflows.descendant_context_ids(rig.owner, turn.run_id) == [child["context_id"], grandchild["context_id"]]


@pytest.mark.asyncio
async def test_missing_child_genesis_with_unknown_plugin_state_is_held(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    child["genesis"]["requires_state_adapter"] = True
    AgentContext.remove(child["context_id"])
    with pytest.raises(runtime.RecoveryHeld, match="child_genesis_state_adapter_required"):
        workflows._submit(turn, child)
    assert rig.owner.sync("list_run_headers", context_id=child["context_id"]) == []


@pytest.mark.asyncio
async def test_background_start_does_not_collect_even_immediately_completed_children(rig, monkeypatch):
    import json
    turn = parent_turn(rig)
    args = {"tool_calls": [{"tool_name": "synthetic_tool", "tool_args": {}}], "wait": False}
    tool = SimpleNamespace(agent=turn.agent)
    def submit(owner_turn, child):
        finish_child(owner_turn, child, terminal="Fast child")
        return SimpleNamespace(result=AsyncMock(return_value="Fast child"))
    monkeypatch.setattr(workflows, "_submit", submit)
    response = await workflows.execute_parallel(tool, args)
    payload = json.loads(response.message)
    assert payload["status"] == "started"
    assert not getattr(tool, "_durable_collection", [])
    assert payload["jobs"][0]["job_id"] in workflows._inventory(turn)
    assert not [call for call in rig.owner.sync("calls", turn.run_id) if call["kind"] == "child_join"]


@pytest.mark.asyncio
@pytest.mark.parametrize("recovered", [False, True])
async def test_saved_manifest_admission_preserves_recovery_target_gate(rig, monkeypatch, recovered):
    from tools.wait import WaitTool
    effects = []
    async def external_body(self, **kwargs):
        effects.append("effect")
        return Response("Synthetic external result", False)
    monkeypatch.setattr(WaitTool, "execute", external_body)
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        WaitTool(self, name, method, args, message, loop_data))
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "wait", "args": {"seconds": 0}}])
    assert not rig.owner.sync("list_run_headers", context_id=child["context_id"])
    turn.recovered = recovered
    if recovered:
        AgentContext.remove(child["context_id"])
    task = workflows._submit(turn, child)
    await task.result_async()
    run = workflows._child_run(rig.owner, child)
    assert run["status"] == ("attention" if recovered else "completed")
    assert effects == ([] if recovered else ["effect"])


@pytest.mark.asyncio
async def test_known_wait_timeout_allocates_a_new_read_only_join_attempt(rig):
    turn = parent_turn(rig)
    child, = await workflows._manifest(turn, [{"name": "synthetic_tool", "args": {}}])
    finish_child(turn, child)
    identifier = workflows._key(turn, "join:" + child["job_id"])
    rig.owner.sync("start_call", turn.run_id, identifier, "child_join", {"job_id": child["job_id"]})
    rig.owner.sync("finish_call", turn.run_id, identifier, {"state": "running", "wait_timed_out": True})
    result = await workflows._join(turn, child, SimpleNamespace(result=AsyncMock(return_value="Done")))
    assert result["state"] == "success"
    assert rig.owner.sync("get_call", turn.run_id, identifier)["result"]["wait_timed_out"]
    assert rig.owner.sync("get_call", turn.run_id, identifier + ":wait:1")["result"] == result


@pytest.mark.asyncio
async def test_timed_out_live_child_can_collect_later_and_release_parent_retention(rig, monkeypatch):
    import json
    import threading
    from helpers import parallel_tools
    from tools.wait import WaitTool
    release, started = threading.Event(), threading.Event()
    effects = []
    async def body(self, **kwargs):
        effects.append("once")
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.005)
        return Response("Child done", False)
    monkeypatch.setattr(WaitTool, "execute", body)
    monkeypatch.setattr(Agent, "get_tool", lambda self, name, method, args, message, loop_data:
                        WaitTool(self, name, method, args, message, loop_data))
    monkeypatch.setattr(parallel_tools, "coerce_timeout", lambda value: 0.05)
    turn = parent_turn(rig)
    tool = SimpleNamespace(agent=turn.agent)
    response = await workflows.execute_parallel(tool, {"tool_calls": [{"tool_name": "wait", "tool_args": {"seconds": 0}}], "wait": True})
    payload = json.loads(response.message)
    assert payload["status"] == "waiting" and payload["jobs"][0]["wait_timed_out"]
    job_id = payload["jobs"][0]["job_id"]
    child = workflows._inventory(turn)[job_id]
    context = AgentContext.get(child["context_id"])
    task = context.task
    assert started.is_set() and task.is_alive() and not tool._durable_collection
    join, = [call for call in rig.owner.sync("calls", turn.run_id) if call["kind"] == "child_join"]
    assert join["status"] == "completed" and join["result"]["wait_timed_out"]
    rig.owner.sync("transition", turn.run_id, "completed", status="completed")
    release.set()
    assert await task.result_async() == "Child done"
    run = rig.owner.sync("admit", rig.context.id, "collect-after-timeout", {}, codec.checkpoint(turn.agent))
    collector = runtime.Turn(rig.owner, turn.agent, run)
    collector.active_call_id = "tool:1:0"
    rig.context._durable_turn = collector
    monkeypatch.setattr(parallel_tools, "coerce_timeout", lambda value: 2)
    result = await workflows.execute_parallel(tool, {"action": "collect", "job_ids": [job_id]})
    assert json.loads(result.message)["status"] == "success"
    await workflows.collect(tool)
    rig.owner.sync("transition", collector.run_id, "completed", status="completed")
    protected = workflows.protected_run_ids(rig.owner)
    assert turn.run_id not in protected
    rig.owner.sync("compact", retain_terminal=0, max_age_days=None, protected_run_ids=protected)
    assert next(row for row in rig.owner.sync("list_run_headers") if row["run_id"] == turn.run_id)["payloads_pruned"]
    assert effects == ["once"] and rig.requests == []
