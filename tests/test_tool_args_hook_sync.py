"""Regression: tool_execute_before hook mutations must reach tool execution.

On the Responses dispatch path (``Agent._execute_tool_request``), a Tool may
hold a different ``args`` object than the caller's ``tool_args`` (MCP tools
start with ``args={}``; a subclass may also copy).  ``tool_execute_before``
extensions mutate ``tool_args`` in place (documented contract — e.g. secret
placeholder substitution).  Without rebinding ``tool.args = tool_args`` after
the hook, tools that read ``self.args`` still see the pre-hook values.

Fix under test: all three dispatch paths re-bind ``tool.args`` immediately
after the hook and before ``tool.execute(**tool_args)``.
"""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

import agent as agent_module
from helpers import extension as extension_module
from helpers import parallel_tools
from helpers.tool import Response

SENTINEL = "SUBSTITUTED_VALUE"


class _FakeLog:
    def log(self, **kwargs):
        return SimpleNamespace(**kwargs)


class _FakeContext:
    def __init__(self) -> None:
        self.log = _FakeLog()


class _FakeLoopData:
    def __init__(self) -> None:
        self.current_tool = None


class RecordingTool:
    """Minimal Tool double: constructed like helpers.tool.Tool with its own args."""

    instances: list["RecordingTool"] = []

    def __init__(self, agent, name, method, args, message, loop_data, **kwargs) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args
        self.message = message
        self.loop_data = loop_data
        self.execute_kwargs: dict | None = None
        self.args_at_execute: dict | None = None
        RecordingTool.instances.append(self)

    async def before_execution(self, **kwargs) -> None:
        return None

    async def execute(self, **kwargs) -> Response:
        self.execute_kwargs = dict(kwargs)
        self.args_at_execute = self.args
        return Response(message="ok", break_loop=False)

    async def after_execution(self, response) -> None:
        return None


def _install_in_place_hook(monkeypatch, target_module) -> None:
    """Fake tool_execute_before: mutates tool_args in place (hook contract)."""

    async def fake_call_extensions_async(extension_point, agent=None, **kwargs):
        if extension_point == "tool_execute_before":
            tool_args = kwargs.get("tool_args") or {}
            tool_args.clear()
            tool_args.update({"secret": SENTINEL})
        return None

    monkeypatch.setattr(target_module, "call_extensions_async", fake_call_extensions_async)


def _stub_mcp_lookup(monkeypatch) -> None:
    """Avoid importing the real mcp_handler (needs the optional ``mcp`` package)."""
    fake = types.ModuleType("helpers.mcp_handler")
    fake.MCPConfig = SimpleNamespace(
        get_instance=lambda: SimpleNamespace(
            get_tool=lambda agent, tool_name: None,
        )
    )
    monkeypatch.setitem(sys.modules, "helpers.mcp_handler", fake)


class _SyncAgent:
    """Duck-typed agent exposing only what the dispatch paths touch."""

    def __init__(self) -> None:
        self.context = _FakeContext()
        self.loop_data = _FakeLoopData()
        self.agent_name = "test"

    async def handle_intervention(self) -> None:
        return None

    async def validate_tool_request(self, tool_request) -> None:
        return None

    def get_tool(self, name, method, args, message, loop_data, **kwargs):
        # Simulate the production fork: Tool constructed with a COPY so
        # tool.args starts as a different object than the caller's dict.
        return RecordingTool(
            agent=self,
            name=name,
            method=method,
            args=dict(args),
            message=message,
            loop_data=loop_data,
        )


def test_responses_path_hook_mutation_reaches_execute_and_tool_args(monkeypatch) -> None:
    """_execute_tool_request: in-place hook mutation lands in kwargs AND tool.args."""
    RecordingTool.instances = []
    _stub_mcp_lookup(monkeypatch)
    _install_in_place_hook(monkeypatch, extension_module)
    fake_agent = _SyncAgent()

    tool_args = {"secret": "ORIGINAL_VALUE"}
    result = asyncio.run(
        agent_module.Agent._execute_tool_request(
            fake_agent,
            tool_name="argstest",
            tool_args=tool_args,
            message="msg",
        )
    )

    assert result is None
    assert len(RecordingTool.instances) == 1
    tool = RecordingTool.instances[0]

    assert tool.execute_kwargs == {"secret": SENTINEL}
    assert tool.args_at_execute is tool_args
    assert tool.args_at_execute == {"secret": SENTINEL}


def test_process_tools_path_hook_mutation_reaches_execute_and_tool_args(
    monkeypatch,
) -> None:
    """process_tools: in-place hook mutation lands in kwargs AND tool.args."""
    RecordingTool.instances = []
    _stub_mcp_lookup(monkeypatch)
    _install_in_place_hook(monkeypatch, extension_module)
    fake_agent = _SyncAgent()

    msg = '{"tool_name": "argstest", "tool_args": {"secret": "ORIGINAL_VALUE"}}'
    result = asyncio.run(agent_module.Agent.process_tools(fake_agent, msg))

    assert result is None
    assert len(RecordingTool.instances) == 1
    tool = RecordingTool.instances[0]

    assert tool.execute_kwargs == {"secret": SENTINEL}
    assert tool.args_at_execute == {"secret": SENTINEL}


@pytest.mark.asyncio
async def test_parallel_path_hook_mutation_reaches_tool_args_after_copy_fork(
    monkeypatch,
) -> None:
    """execute_tool_call: rebind after hook keeps tool.args aligned with mutations."""
    observed: dict = {}

    class FakeTool:
        def __init__(self, args):
            self.args = args

        def get_log_object(self):
            return None

        async def before_execution(self, **kwargs):
            pass

        async def execute(self, **kwargs):
            observed["tool_args"] = self.args
            observed["kwargs"] = dict(kwargs)
            return Response(message="done", break_loop=False)

        async def after_execution(self, response):
            pass

    class FakeAgent:
        context = SimpleNamespace()
        loop_data = SimpleNamespace(current_tool=None)

        def get_tool(self, **kwargs):
            return FakeTool(dict(kwargs["args"]))

        async def handle_intervention(self):
            pass

    async def mutate_hook(extension_point, agent=None, **kwargs):
        if extension_point != "tool_execute_before":
            return
        tool_args = kwargs["tool_args"]
        tool_args.clear()
        tool_args.update({"secret": SENTINEL})

    monkeypatch.setattr(parallel_tools, "call_extensions_async", mutate_hook)
    worker_args = {"secret": "ORIGINAL_VALUE"}

    result = await parallel_tools.execute_tool_call(
        FakeAgent(),  # type: ignore[arg-type]
        "argstest",
        worker_args,
    )

    assert result == "done"
    assert observed["kwargs"] == {"secret": SENTINEL}
    assert observed["tool_args"] is worker_args
    assert observed["tool_args"] == {"secret": SENTINEL}
