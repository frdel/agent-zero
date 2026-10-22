from pathlib import Path
from types import SimpleNamespace

from helpers.mcp_handler import MCPTool
from helpers.parallel_tools import ParallelJob, _log_parallel_child_started
from helpers.tool import Tool, Response
from tools.call_subordinate import Delegation
from tools.unknown import Unknown


class _GenericTool(Tool):
    async def execute(self, **kwargs):
        return Response(message="", break_loop=False)


class _FakeLog:
    def log(self, **kwargs) -> dict:
        return kwargs


class _FakeAgent:
    agent_name = "Zero"

    def __init__(self) -> None:
        self.context = SimpleNamespace(log=_FakeLog())


def _make(tool_cls, name: str, method: str = "execute"):
    return tool_cls(
        agent=_FakeAgent(), name=name, method=method, args={}, message="", loop_data=None
    )


def test_call_subordinate_heading_has_no_agent_prefix():
    entry = _make(Delegation, "call_subordinate").get_log_object()

    assert entry["heading"] == "icon://communication Calling Subordinate Agent"


def test_unknown_heading_has_no_agent_prefix():
    tool = _make(Unknown, "unknown")

    assert tool.get_log_object()["heading"] == "icon://construction Using tool 'unknown:execute'"

    tool = _make(Unknown, "unknown", method="")

    assert tool.get_log_object()["heading"] == "icon://construction Using tool 'unknown'"


def test_parallel_subordinate_start_row_has_no_agent_prefix():
    job = ParallelJob(
        id="job-1",
        parent_context_id="ctx-1",
        index=0,
        tool_name="call_subordinate",
        tool_args={"message": "demo"},
        kind="subordinate",
        log_id="log-1",
    )

    _log_parallel_child_started(_FakeAgent(), job)

    assert job.log_item["heading"] == "icon://communication Calling Subordinate Agent"


def test_mcp_tool_heading_has_no_agent_prefix():
    entry = _make(MCPTool, "server.tool").get_log_object()

    assert entry["heading"] == "icon://extension Using MCP tool 'server.tool'"
    assert entry["kvps"]["tool_name"] == "server.tool"


def test_generic_tool_fallback_heading_has_no_agent_prefix():
    entry = _make(_GenericTool, "mystery_tool").get_log_object()

    assert entry["heading"] == "icon://construction Using tool 'mystery_tool:execute'"


def test_parallel_generic_tool_start_row_has_no_agent_prefix():
    job = ParallelJob(
        id="job-2",
        parent_context_id="ctx-1",
        index=0,
        tool_name="mystery_tool",
        tool_args={},
        kind="tool",
        log_id="log-2",
    )

    _log_parallel_child_started(_FakeAgent(), job)

    assert job.log_item["heading"] == "icon://construction Using tool 'mystery_tool'"


def test_generic_fallback_sources_avoid_the_agent_prefix():
    root = Path(__file__).resolve().parents[1]

    for rel in (
        "plugins/_code_execution/tools/input.py",
        "plugins/_text_editor/helpers/log.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "agent_name}: Using tool" not in text, rel
