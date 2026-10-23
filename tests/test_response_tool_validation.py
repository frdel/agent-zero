import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helpers.errors import RepairableException
from helpers.log import Log
from tools.response import ResponseTool


@pytest.mark.asyncio
@pytest.mark.parametrize("args", [{"text": "ok"}, {"message": "ok"}])
async def test_response_tool_accepts_text_or_message(args) -> None:
    tool = ResponseTool(None, "response", None, args, "", None)

    response = await tool.execute()

    assert response.message == "ok"
    assert response.break_loop is True


@pytest.mark.asyncio
async def test_response_tool_uses_non_empty_legacy_message_fallback() -> None:
    tool = ResponseTool(
        None,
        "response",
        None,
        {"text": "", "message": "legacy"},
        "",
        None,
    )

    response = await tool.execute()

    assert response.message == "legacy"
    assert response.break_loop is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": None},
        {"message": "\n\t"},
    ],
)
async def test_response_tool_rejects_empty_arguments(args) -> None:
    tool = ResponseTool(None, "response", None, args, "", None)

    with pytest.raises(RepairableException, match="non-empty top-level"):
        await tool.execute()


@pytest.mark.asyncio
async def test_response_tool_rejects_nested_response_args() -> None:
    tool = ResponseTool(
        None,
        "response",
        None,
        {
            "thoughts": [],
            "headline": "Providing exact payload",
            "tool_name": "response",
            "tool_args": {"text": "nested"},
        },
        "",
        None,
    )

    with pytest.raises(RepairableException, match="non-empty top-level"):
        await tool.execute()


@pytest.mark.asyncio
@pytest.mark.parametrize("streamed", [True, False])
async def test_response_tool_finishes_one_bubble_with_or_without_streaming(streamed):
    log = Log()
    generating = log.log(type="agent", id="generation")
    loop_data = SimpleNamespace(params_temporary={"log_item_generating": generating})
    agent = SimpleNamespace(agent_name="A0", context=SimpleNamespace(log=log))
    if streamed:
        loop_data.params_temporary["log_item_response"] = log.log(
            type="response", id=generating.id, content="done"
        )
    tool = ResponseTool(agent, "response", None, {"text": "done"}, "", loop_data)
    await tool.before_execution()
    result = await tool.execute()
    await tool.after_execution(result)
    responses = [item for item in log.logs if item.type == "response"]
    assert len(responses) == 1
    assert responses[0].content == "done"
    assert responses[0].id == generating.id
    assert responses[0].kvps["finished"] is True
