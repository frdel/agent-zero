"""Kill actual framework runners at committed call boundaries, then restart."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX pipe barrier; Windows store lock tested separately")
@pytest.mark.parametrize("scenario,expected_status,effects", [
    ("model_result", "completed", 0),
    ("safe_intent", "completed", 0),
    ("never_body", "attention", 1),
    ("native_finalized", "completed", 1),
    ("model_intent", "attention", 0),
])
def test_process_kill_then_framework_recovery(tmp_path, scenario, expected_status, effects):
    args = [sys.executable, str(Path(__file__).resolve()), "--child", str(tmp_path), scenario]
    child = subprocess.Popen(args + ["crash"], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            if child.poll() is not None:
                out, err = child.communicate()
                pytest.fail(f"Child exited before barrier: {out!r} {err!r}")
            if (tmp_path / "barrier").exists():
                break
            select.select([child.stdout], [], [], 0.05)
            # Drain framework printing so it cannot block the child before the barrier.
            if select.select([child.stdout], [], [], 0)[0]:
                os.read(child.stdout.fileno(), 65536)
        else:
            pytest.fail("Runner did not reach the requested commit barrier")
        child.kill()
        child.communicate(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    restarted = subprocess.run(args + ["recover"], cwd=PROJECT, capture_output=True, timeout=20)
    assert restarted.returncode == 0, restarted.stderr.decode()
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["status"] == expected_status
    assert summary["provider_calls"] == (0 if scenario == "model_intent" else 1)
    assert summary["effects"] == effects
    if expected_status == "completed":
        assert summary["answer"] == "Done"
    if scenario == "native_finalized":
        assert summary["tool_output_ids"] == ["effect-call"]
        assert summary["history_count"] == 3


def child_main(root, scenario, action):
    sys.path.insert(0, str(PROJECT))
    import asyncio
    import threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from agent import Agent, AgentConfig, AgentContext, UserMessage
    from helpers import extension, persist_chat, responses_history
    from helpers.durable import runtime
    from helpers.llm_result import LLMResult, result_from_metadata
    from helpers.tool import Tool, Response
    from tools.response import ResponseTool
    from langchain_core.messages import HumanMessage
    import helpers.secrets
    import helpers.log
    import helpers.mcp_handler
    import helpers.state_monitor_integration

    root = Path(root)
    extension._get_extension_classes = lambda *args, **kwargs: []
    AgentContext._contexts = {}
    persist_chat.CHATS_FOLDER = str(root / "chats")
    persist_chat.initialize_agent = lambda **kwargs: AgentConfig(mcp_servers="")
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

    def record(name):
        with (root / name).open("a") as handle:
            handle.write("1\n")
            handle.flush()
            os.fsync(handle.fileno())

    class Model:
        model_name = "loopback-fake-provider"
        kwargs = {"a0_api_mode": "chat_completions"}

        async def unified_turn(self, **kwargs):
            record("provider")
            if scenario == "native_finalized":
                return LLMResult.from_response({"id": "resp-a", "output": [
                    {"type": "function_call", "name": "effect", "call_id": "effect-call", "arguments": "{}"},
                    {"type": "function_call", "name": "response", "call_id": "response-call", "arguments": '{"text":"Done"}'},
                ]})
            tool = "effect" if scenario == "never_body" else "response"
            return LLMResult.from_chat(response=json.dumps({"tool_name": tool, "tool_args": {"text": "Done"}}))

    class Effect(Tool):
        async def execute(self, **kwargs):
            record("effects")
            return Response("Effect completed", False)

    Agent.get_chat_model = lambda self: Model()
    Agent.get_tool = lambda self, name, method, args, message, loop_data: (
        ResponseTool if name == "response" else Effect)(self, name, method, args, message, loop_data)
    owner = runtime.RecoveryService(root / "durable")
    runtime._service = owner
    original = owner.io

    async def commit_barrier(method, *args, **kwargs):
        result = await original(method, *args, **kwargs)
        selected = (
            (scenario == "model_result" and method == "finish_call" and args[1] == "model:0")
            or (scenario == "safe_intent" and method == "start_call" and args[1] == "tool:0:0")
            or (scenario == "never_body" and method == "finish_call" and args[1] == "tool:0:0")
            or (scenario == "native_finalized" and method == "finish_call" and args[1] == "tool:0:0:final")
            or (scenario == "model_intent" and method == "start_call" and args[1] == "model:0")
        )
        if action == "crash" and selected:
            with (root / "barrier").open("w") as handle:
                handle.write("committed")
                handle.flush()
                os.fsync(handle.fileno())
            threading.Event().wait()
        return result

    owner.io = commit_barrier
    try:
        if action == "crash":
            context = AgentContext(AgentConfig(mcp_servers=""), id="process-test")
            task = context.communicate(UserMessage("Hello", id="input-1"))
        else:
            owner.recover()
            context = AgentContext.get("process-test")
            task = context.task
        answer = task.result_sync(timeout=10)
        run, = owner.sync("list_runs")
        ids = []
        for message in context.agent0.history.all_messages():
            result = result_from_metadata(message.metadata)
            if result and not message.ai:
                ids.extend(item.get("call_id") for item in result.input_items)
        summary = {"status": run["status"], "answer": answer,
                   "provider_calls": len((root / "provider").read_text().splitlines()) if (root / "provider").exists() else 0,
                   "effects": len((root / "effects").read_text().splitlines()) if (root / "effects").exists() else 0,
                   "tool_output_ids": ids, "history_count": len(context.agent0.history.all_messages())}
        (root / "summary.json").write_text(json.dumps(summary))
    finally:
        owner.close()


if __name__ == "__main__":
    child_main(*sys.argv[2:])
