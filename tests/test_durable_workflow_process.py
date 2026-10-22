"""Restart real scheduler/child coordinators after committed workflow boundaries."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process barrier")
@pytest.mark.parametrize("scenario", [
    "scheduler_projection", "scheduler_model_result", "parallel_join", "parallel_join_unaudited",
    "parallel_unknown", "subordinate_completed", "creation_unknown",
])
def test_workflow_survives_process_kill(tmp_path, scenario):
    args = [sys.executable, str(Path(__file__).resolve()), "--child", str(tmp_path), scenario]
    child = subprocess.Popen(args + ["crash"], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 20
        while not (tmp_path / "barrier").exists():
            if child.poll() is not None:
                out, err = child.communicate()
                pytest.fail(f"Child exited before barrier: {out!r} {err!r}")
            if time.monotonic() >= deadline:
                pytest.fail("Workflow did not reach the committed crash boundary")
            if select.select([child.stdout], [], [], .05)[0]:
                os.read(child.stdout.fileno(), 65536)
        child.kill()
        child.communicate(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    restarted = subprocess.run(args + ["recover"], cwd=PROJECT, capture_output=True, timeout=25)
    assert restarted.returncode == 0, restarted.stderr.decode()
    result = json.loads((tmp_path / "summary.json").read_text())
    if scenario.startswith("scheduler"):
        assert result["status"] == "completed"
        assert result["provider_calls"] == 1
        assert result["task_state"] == "idle" and result["task_result"] == "Done"
        assert result["plan_done"] == 1 and result["plan_todo"] == 1
    elif scenario == "parallel_join":
        assert result["status"] == "completed"
        assert result["provider_calls"] == 1
        assert result["effects"] == ["first", "second"]
        assert result["native_output_ids"] == ["parallel-call"]
        assert result["child_statuses"] == ["completed", "completed"]
    elif scenario == "parallel_unknown":
        assert result["status"] == "attention"
        assert result["provider_calls"] == 1
        assert result["effects"] == ["first", "second"]
        assert sorted(result["child_statuses"]) == ["attention", "completed"]
    elif scenario == "parallel_join_unaudited":
        assert result["status"] == "attention"
        assert result["provider_calls"] == 1
        assert result["effects"] == ["first"]
        assert sorted(result["child_statuses"]) == ["attention", "completed"]
    elif scenario == "subordinate_completed":
        assert result["status"] == "completed"
        assert result["provider_calls"] == 3
        assert result["child_statuses"] == ["completed"]
    else:
        assert result["status"] == "attention"
        assert result["provider_calls"] == 1 and result["child_statuses"] == []


def child_main(root, scenario, action):
    sys.path.insert(0, str(PROJECT))
    import asyncio
    from datetime import datetime, timedelta, timezone
    import threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agent import Agent, AgentConfig, AgentContext, UserMessage
    from helpers import extension, persist_chat, responses_history, parallel_tools, task_scheduler
    from helpers.durable import runtime
    from helpers.llm_result import LLMResult, result_from_metadata
    from helpers.tool import Tool, Response
    from tools.response import ResponseTool
    from tools.parallel import ParallelTool
    from tools.call_subordinate import Delegation
    import tools.call_subordinate as delegation
    from langchain_core.messages import HumanMessage
    import helpers.secrets
    import helpers.log
    import helpers.mcp_handler
    import helpers.state_monitor_integration

    root = Path(root)
    extension._get_extension_classes = lambda *args, **kwargs: []
    AgentContext._contexts = {}
    config = AgentConfig(mcp_servers="")
    persist_chat.CHATS_FOLDER = str(root / "chats")
    persist_chat.initialize_agent = lambda **kwargs: config
    task_scheduler.SCHEDULER_FOLDER = str(root / "scheduler")
    task_scheduler.initialize_agent = lambda **kwargs: config
    delegation.initialize_agent = lambda **kwargs: config
    responses_history.prepare_call = lambda *args: {}
    helpers.state_monitor_integration.mark_dirty_all = lambda **kwargs: None
    helpers.state_monitor_integration.mark_dirty_for_context = lambda *args, **kwargs: None
    manager = SimpleNamespace(mask_values=lambda value: value)
    helpers.secrets.get_secrets_manager = lambda context: manager
    helpers.log.get_secrets_manager = lambda context: manager
    helpers.mcp_handler.MCPConfig.get_instance = lambda: SimpleNamespace(get_tool=lambda *args: None)
    Agent.prepare_prompt = AsyncMock(return_value=[HumanMessage(content="Synthetic")])
    Agent.parse_prompt = lambda self, name, **kwargs: kwargs.get("message", "")
    Agent.read_prompt = lambda *args, **kwargs: "Synthetic"

    def record(name, value):
        with (root / name).open("a") as handle:
            handle.write(value + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def barrier():
        (root / "barrier").write_text("committed")
        threading.Event().wait()

    class Model:
        model_name = "synthetic-workflow-provider"
        kwargs = {"a0_api_mode": "chat_completions"}

        def __init__(self, agent):
            self.agent = agent

        async def unified_turn(self, **kwargs):
            record("provider", self.agent.context.id)
            if scenario.startswith("scheduler") or self.agent.number > 0:
                return LLMResult.from_chat(response='{"tool_name":"response","tool_args":{"text":"Done"}}')
            if scenario.startswith("parallel"):
                args = {"tool_calls": [
                    {"tool_name": "effect", "tool_args": {"value": "first"}},
                    {"tool_name": "effect", "tool_args": {"value": "second"}},
                ]}
                return LLMResult.from_response({"id": "resp-workflow", "output": [
                    {"type": "function_call", "name": "parallel", "call_id": "parallel-call", "arguments": json.dumps(args)},
                    {"type": "function_call", "name": "response", "call_id": "response-call", "arguments": '{"text":"Done"}'},
                ]})
            if not any(message.ai for message in self.agent.history.all_messages()):
                return LLMResult.from_chat(response='{"tool_name":"call_subordinate","tool_args":{"message":"Child assignment","reset":true}}')
            return LLMResult.from_chat(response='{"tool_name":"response","tool_args":{"text":"Done"}}')

    class Effect(Tool):
        async def execute(self, value="", **kwargs):
            record("effects", value)
            if scenario == "parallel_unknown" and value == "second" and action == "crash":
                await asyncio.Future()
            return Response(value, False)

    if scenario == "parallel_join":
        # Explicit test-only portability audit: this stateless target is the
        # same temporary side-effect recorder in both processes. It remains
        # replay=never, so an unknown completed effect is never repeated.
        from helpers.durable import codec, replay
        replay.AUDITED_TOOLS.add((Effect.__name__, codec.identity(Effect)["source"]))

    Agent.get_chat_model = lambda self: Model(self)

    def resolve(agent, name, method, args, message, loop_data):
        cls = {"parallel": ParallelTool, "call_subordinate": Delegation, "response": ResponseTool}.get(name, Effect)
        return cls(agent, name, method, args, message, loop_data)

    Agent.get_tool = resolve
    parallel_tools._resolve_parallel_tool = lambda agent, name, args, **kwargs: resolve(agent, name, None, args, "", agent.loop_data)
    owner = runtime.RecoveryService(root / "durability")
    runtime._service = owner
    original = owner.io

    async def commit_barrier(method, *args, **kwargs):
        # Keep child two durably admitted but entirely unstarted in the success
        # scenario; in the uncertainty scenario it records an external effect.
        if scenario in ("parallel_join", "parallel_join_unaudited") and action == "crash" and method == "get_run":
            row = owner.sync("get_run", args[0])
            origin = (row.get("checkpoint") or {}).get("origin") or {}
            if origin.get("tool_args", {}).get("value") == "second":
                await asyncio.Future()
        if action == "crash" and scenario == "scheduler_projection" and method == "start_call" and args[1] == "scheduler:complete":
            barrier()
        result = await original(method, *args, **kwargs)
        if action == "crash":
            selected = (
                (scenario == "scheduler_model_result" and method == "finish_call" and args[1] == "model:0")
                or (scenario in ("parallel_join", "parallel_join_unaudited", "parallel_unknown") and method == "finish_call" and ":join:" in args[1])
                or (scenario == "creation_unknown" and method == "start_call" and args[1].endswith(":workflow"))
            )
            if scenario == "subordinate_completed" and method == "transition" and kwargs.get("status") == "completed":
                row = owner.sync("get_run", args[0])
                selected = ((row.get("checkpoint") or {}).get("origin") or {}).get("kind") == "child"
            if selected:
                if scenario == "parallel_unknown":
                    while not (root / "effects").exists() or "second" not in (root / "effects").read_text():
                        await asyncio.sleep(.01)
                barrier()
        return result

    owner.io = commit_barrier
    engine = task_scheduler.TaskScheduler.get() if scenario.startswith("scheduler") else None
    try:
        if action == "crash":
            context = AgentContext(config, id="workflow-parent")
            if engine:
                now = datetime(2026, 10, 22, tzinfo=timezone.utc)
                scheduled = task_scheduler.PlannedTask(uuid="scheduled-owner", name="Synthetic", system_prompt="", prompt="Work",
                    context_id=context.id, plan=task_scheduler.TaskPlan(todo=[now-timedelta(days=1), now+timedelta(days=3650)]))
                asyncio.run(engine._tasks.add_task(scheduled))
                asyncio.run(engine._run_task(scheduled))
                task = context.task
            else:
                task = context.communicate(UserMessage("Hello", id="root-input"))
        else:
            owner.recover()
            context = AgentContext.get("workflow-parent")
            task = context.task
        if owner.distributed:
            # Shared scheduler admission returns a ledger handle; the poller
            # may execute it in a different reconstructed context or host.
            header = next(row for row in owner.sync("list_run_headers") if row["context_id"] == "workflow-parent")
            task = owner.dispatch_for_run(header["run_id"])
        task.result_sync(timeout=15)
        runs = owner.sync("list_runs")
        parent = next(run for run in runs if run["context_id"] == context.id)
        children = [run for run in runs if ((run.get("checkpoint") or {}).get("origin") or {}).get("kind") == "child"]
        # All child effects are recorded outside the journal, independently of
        # the return value or recovery projection under test.
        effects = (root / "effects").read_text().splitlines() if (root / "effects").exists() else []
        ids = []
        for message in context.agent0.history.all_messages():
            result = result_from_metadata(message.metadata)
            if result and not message.ai:
                ids.extend(item.get("call_id") for item in result.input_items if item.get("call_id") == "parallel-call")
        summary = {"status": parent["status"], "provider_calls": len((root / "provider").read_text().splitlines()),
                   "effects": effects, "child_statuses": [run["status"] for run in children], "native_output_ids": ids}
        if engine:
            asyncio.run(engine.reload())
            scheduled = engine.get_task_by_uuid("scheduled-owner")
            summary.update(task_state=scheduled.state.value, task_result=scheduled.last_result,
                           plan_done=len(scheduled.plan.done), plan_todo=len(scheduled.plan.todo))
        (root / "summary.json").write_text(json.dumps(summary))
    finally:
        owner.close()


if __name__ == "__main__":
    child_main(*sys.argv[2:])
