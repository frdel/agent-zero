from types import SimpleNamespace

import pytest

from agent import LoopData
from extensions.python._functions.agent.Agent.hist_add_ai_response.end._10_log_plain_responses import (
    LogPlainResponses,
)
from extensions.python.response_stream._10_log_from_stream import (
    LogFromStream as StreamLog,
)
from extensions.python.response_stream._20_live_response import LiveResponse
from helpers.dirty_json import DirtyJson
from helpers.log import Log


def _agent_with_generating_log():
    log = Log()
    item = log.log(type="agent", heading="A0: Calling LLM...", id="msg-1")
    agent = SimpleNamespace(
        loop_data=SimpleNamespace(params_temporary={"log_item_generating": item})
    )
    return agent, item


def test_log_keyword_updates_share_kvp_value_limit():
    item = Log().log(type="agent", heading="A0: Reasoning")

    item.update(reasoning="r" * 6_000, finished=True)

    assert len(item.kvps["reasoning"]) <= 5_000
    assert "Characters hidden" in item.kvps["reasoning"]
    assert item.kvps["finished"] is True


def test_live_log_updates_omit_unchanged_collections(monkeypatch):
    import helpers.log as log_module

    full_dirty: list[str | None] = []
    context_dirty: list[tuple[str, str | None, bool]] = []
    monkeypatch.setattr(
        log_module,
        "_MARK_DIRTY_ALL",
        lambda *, reason=None: full_dirty.append(reason),
    )
    monkeypatch.setattr(
        log_module,
        "_MARK_DIRTY_FOR_CONTEXT",
        lambda context_id, *, reason=None, include_collections=True: context_dirty.append(
            (context_id, reason, include_collections)
        ),
    )

    log = Log()
    log.context = SimpleNamespace(id="ctx", streaming_agent=None)
    item = log.log(type="agent", heading="Calling LLM")
    item.update(content="stream update")
    log.set_progress("Receiving")

    assert full_dirty == ["log.Log._notify_state_monitor"]
    assert context_dirty == [
        ("ctx", "log.Log._update_item", False),
        ("ctx", "log.Log.set_progress", False),
    ]


def test_responses_plain_text_completion_finishes_generating_log_as_response():
    agent, item = _agent_with_generating_log()
    data = {
        "args": (agent, "Plain final answer."),
        "kwargs": {"id": "msg-1", "llm_result": SimpleNamespace(mode="responses")},
    }

    LogPlainResponses(agent=agent).execute(data=data)

    assert item.type == "response"
    assert item.heading == ""
    assert item.content == "Plain final answer."
    assert item.update_progress == "none"
    assert item.kvps["finished"] is True
    assert agent.loop_data.params_temporary["log_item_response"] is item


def test_responses_tool_json_keeps_generating_log_as_agent_step():
    agent, item = _agent_with_generating_log()
    data = {
        "args": (
            agent,
            '{"tool_name":"search_engine","tool_args":{"query":"today news"}}',
        ),
        "kwargs": {"id": "msg-1", "llm_result": SimpleNamespace(mode="responses")},
    }

    LogPlainResponses(agent=agent).execute(data=data)

    assert item.type == "agent"
    assert item.heading == "A0: Calling LLM..."
    assert item.content == ""
    assert "log_item_response" not in agent.loop_data.params_temporary


@pytest.mark.parametrize("status", ["rejected", "truncated"])
def test_rejected_leaked_call_is_not_displayed_as_a_final_response(status):
    agent, item = _agent_with_generating_log()
    agent.loop_data.params_temporary["leaked_tool_call"] = status
    LogPlainResponses(agent).execute(data={
        "args": (agent, '<tool_call>{"name":"response","arguments":{"text":"half'),
        "kwargs": {"llm_result": SimpleNamespace(mode="responses")},
    })
    assert item.type == "agent"
    assert "log_item_response" not in agent.loop_data.params_temporary


def test_responses_plain_json_completion_finishes_generating_log_as_response():
    agent, item = _agent_with_generating_log()
    data = {
        "args": (agent, '{"status":"ok"}'),
        "kwargs": {"id": "msg-1", "llm_result": SimpleNamespace(mode="responses")},
    }

    LogPlainResponses(agent=agent).execute(data=data)

    assert item.type == "response"
    assert item.content == '{"status":"ok"}'
    assert agent.loop_data.params_temporary["log_item_response"] is item


def test_responses_plain_text_completion_does_not_replace_live_response_log():
    agent, item = _agent_with_generating_log()
    live_response = Log().log(type="response", content="Already live")
    agent.loop_data.params_temporary["log_item_response"] = live_response
    data = {
        "args": (agent, "Plain final answer."),
        "kwargs": {"id": "msg-1", "llm_result": SimpleNamespace(mode="responses")},
    }

    LogPlainResponses(agent=agent).execute(data=data)

    assert item.type == "agent"
    assert item.content == ""
    assert agent.loop_data.params_temporary["log_item_response"] is live_response


@pytest.mark.asyncio
async def test_live_response_renders_single_action_wrapper():
    log = Log()
    generating = log.log(type="agent", id="msg-1")
    loop_data = SimpleNamespace(params_temporary={"log_item_generating": generating})
    agent = SimpleNamespace(
        context=SimpleNamespace(log=log),
        agent_name="A0",
    )

    await LiveResponse(agent=agent).execute(
        loop_data=loop_data,
        parsed={
            "actions": [
                {"tool_name": "response", "tool_args": {"text": "wrapper works"}}
            ]
        },
    )

    response = loop_data.params_temporary["log_item_response"]
    assert response.type == "response"
    assert response.content == "wrapper works"
    assert response.id == "msg-1"


@pytest.mark.asyncio
async def test_live_response_renders_legacy_message_argument():
    log = Log()
    generating = log.log(type="agent", id="msg-1")
    loop_data = SimpleNamespace(params_temporary={"log_item_generating": generating})
    agent = SimpleNamespace(
        context=SimpleNamespace(log=log),
        agent_name="A0",
    )

    await LiveResponse(agent=agent).execute(
        loop_data=loop_data,
        parsed={"tool_name": "response", "tool_args": {"message": "legacy works"}},
    )

    response = loop_data.params_temporary["log_item_response"]
    assert response.content == "legacy works"
    assert response.id == "msg-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stream", "expected_step"),
    [
        (
            '{"tool_name":"code_execution_tool","tool_args":',
            "Using code_execution_tool...",
        ),
        (
            '{"tool_name":"code_execution_tool","tool_args":'
            '{"runtime":"python","code":',
            "Writing Python code... ",
        ),
        (
            '{"tool_name":"code_execution_tool","tool_args":'
            '{"runtime":"python","code":"pri',
            "Writing Python code... (3)",
        ),
    ],
)
async def test_stream_log_tolerates_partial_tool_arguments(
    stream: str,
    expected_step: str,
):
    log = Log()
    loop_data = LoopData()
    agent = SimpleNamespace(
        context=SimpleNamespace(log=log),
        agent_name="A0",
    )

    await StreamLog(agent=agent).execute(
        loop_data=loop_data,
        text=stream,
        parsed=DirtyJson.parse_string(stream),
    )

    item = loop_data.params_temporary["log_item_generating"]
    assert item.kvps["step"] == expected_step


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_request", [
    {"tool": "code_execution_tool", "args": {"runtime": "python", "code": "print(1)"}},
    {"actions": [{"tool": "code_execution_tool", "args": {"runtime": "python", "code": "print(1)"}}]},
    {"type": "function", "name": "code_execution_tool", "parameters": {"runtime": "python", "code": "print(1)"}},
])
async def test_stream_aliases_reach_all_consumers_canonically(monkeypatch, tool_request):
    import json
    from agent import Agent
    from helpers import extension

    agent = object.__new__(Agent)
    agent.loop_data = LoopData()
    agent.agent_name = "A0"
    agent.context = SimpleNamespace(log=Log())

    async def no_intervention():
        pass

    async def consume(name, _agent, **kwargs):
        assert name == "response_stream"
        assert kwargs["parsed"]["tool_name"] == "code_execution_tool"
        assert kwargs["parsed"]["tool_args"] == {"runtime": "python", "code": "print(1)"}
        await StreamLog(agent=agent).execute(**kwargs)

    agent.handle_intervention = no_intervention
    monkeypatch.setattr(extension, "call_extensions_async", consume)
    await agent.handle_response_stream(json.dumps(tool_request))
    assert agent.loop_data.params_temporary["log_item_generating"].kvps["step"] == "Writing Python code... (8)"


def test_native_tool_commentary_keeps_generating_step():
    from helpers.llm_result import LLMResult
    agent, item = _agent_with_generating_log()
    result = LLMResult.from_response({
        "output_text": "Running the lookup now.",
        "output": [{"type": "function_call", "name": "lookup", "call_id": "call_1", "arguments": '{"q":"a0"}'}],
    })
    LogPlainResponses(agent=agent).execute(data={
        "args": (agent, result.response), "kwargs": {"llm_result": result},
    })
    assert item.type == "agent"
    assert "log_item_response" not in agent.loop_data.params_temporary
