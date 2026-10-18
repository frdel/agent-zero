import json
from types import SimpleNamespace

import pytest
from helpers.llm_result import LLMResult

from extensions.python.message_loop_result import _20_empty_response as empty_response
from extensions.python.message_loop_result._05_truncated_response import TruncatedResponse
from extensions.python.message_loop_result._20_empty_response import EmptyResponse
from extensions.python.message_loop_result._30_repeat_response import RepeatResponse
from extensions.python._functions.agent.Agent.hist_add_warning.end import (
    _90_stop_unusable_response_loop as response_loop,
)


class FakeAgent:
    def __init__(self, response: str, reasoning: str = "", last_response: str = ""):
        self.loop_data = SimpleNamespace(
            last_response=last_response,
            params_temporary={},
            params_persistent={},
            iteration=0,
        )
        self.logs = []
        self.context = SimpleNamespace(
            log=SimpleNamespace(log=lambda **entry: self.logs.append(entry))
        )
        self.agent_name = "A0"
        self.response = response
        self.reasoning = reasoning
        self.warnings = []
        self.history = []

    def read_prompt(self, name, **kwargs):
        if name == "fw.msg_unusable_response_limit.md":
            return f"stopped at {kwargs['limit']}"
        return {
            "fw.msg_misformat.md": "misformatted",
            "fw.msg_empty_response.md": "empty",
            "fw.msg_repeat.md": "repeat",
            "fw.msg_repeat_response.md": "Repeated response detected. Retrying.",
            "fw.msg_reasoning_only.md": "reasoning only",
            "fw.msg_reasoning_only_response.md": "Reasoning-only response detected. Retrying.",
            "fw.msg_output_limit.md": "output limit",
            "fw.msg_output_limit_response.md": f"truncated ({kwargs.get('finish_reason')})",
        }[name]

    def hist_add_ai_response(self, response, **kwargs):
        self.history.append(response)
        return SimpleNamespace(id="assistant")

    def _remember_llm_result_state(self, *args):
        pass

    def hist_add_warning(self, message):
        self.warnings.append(message)
        return SimpleNamespace(id="warning")


def _run(agent, **llm_result):
    result_data = {
        "llm_result": SimpleNamespace(
            response=agent.response, reasoning=agent.reasoning, **llm_result
        )
    }
    TruncatedResponse(agent).execute(result_data)
    EmptyResponse(agent).execute(result_data)
    RepeatResponse(agent).execute(result_data)
    return result_data


def test_empty_result_skips_default_processing():
    agent = FakeAgent("")

    assert _run(agent)["skip_default_processing"] is True
    assert agent.history == []
    assert agent.warnings == []
    assert agent.logs == [{"type": "warning", "content": "empty"}]


def test_empty_result_counts_toward_unusable_response_limit(monkeypatch):
    monkeypatch.setattr(
        empty_response,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 2},
    )
    agent = FakeAgent("")

    assert _run(agent)["skip_default_processing"] is True

    agent.loop_data.iteration = 1
    try:
        _run(agent)
    except response_loop.HandledException as error:
        assert str(error) == "stopped at 2"
    else:
        raise AssertionError("empty response should stop at the configured limit")

    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 2


def test_later_handlers_skip_a_result_already_handled_by_an_extension():
    response = '{"tool_name":"response"}'
    agent = FakeAgent(response, last_response=response)
    result_data = {
        "llm_result": SimpleNamespace(response=response, reasoning=""),
        "skip_default_processing": True,
    }

    EmptyResponse(agent).execute(result_data)
    RepeatResponse(agent).execute(result_data)

    assert agent.history == []
    assert agent.warnings == []


def test_repeat_skips_default_processing():
    agent = FakeAgent('{"tool_name":"response"}', last_response='{"tool_name":"response"}')

    assert _run(agent)["skip_default_processing"] is True
    assert agent.warnings == ["repeat"]
    assert agent.logs == [
        {
            "type": "warning",
            "content": "Repeated response detected. Retrying.",
            "id": "warning",
        }
    ]


def test_repeat_ignores_reasoning():
    response = '{"tool_name":"response"}'
    agent = FakeAgent(response, reasoning="thinking", last_response=response)

    assert _run(agent)["skip_default_processing"] is True
    assert agent.warnings == ["repeat"]


def test_reasoning_only_retries_with_agent_warning():
    agent = FakeAgent("", reasoning="thinking", last_response="previous")

    result = _run(agent)

    assert result["skip_default_processing"] is True
    assert agent.warnings == ["reasoning only"]
    assert agent.logs == [
        {
            "type": "warning",
            "content": "Reasoning-only response detected. Retrying.",
            "id": "warning",
        }
    ]


@pytest.mark.parametrize("old_text,new_text,old_query,new_query,old_batch,new_batch,repeated", [
    ("Working.", "Working.", "first", "first", False, False, True),
    ("Working.", "Different commentary.", "first", "first", False, False, False),
    ("Working.", None, "first", "first", False, False, False),
    (None, "Working.", "first", "first", False, False, False),
    (json.dumps({"tool_name": "lookup", "tool_args": {"q": "first"}}),
     None, "first", "first", False, False, False),
    (None, None, "first", "first", False, False, True),
    ("Working.", "Working.", "first", "second", False, False, False),
    (None, None, "first", "second", False, False, False),
    ("Working.", "Working.", "first", "first", False, True, False),
    ("Working.", "Working.", "first", "first", True, True, True),
    ("Working.", "Different commentary.", "first", "first", True, True, False),
])
def test_native_repeat_compares_complete_public_turn(
    monkeypatch, old_text, new_text, old_query, new_query, old_batch, new_batch, repeated
):
    from agent import Agent, LoopData
    from helpers import extension, history
    from helpers.llm_result import LLMResult, result_from_metadata

    def result(query, commentary, batch, identifier):
        items = [{"type": "reasoning", "encrypted_content": identifier,
                  "summary": [{"type": "summary_text", "text": identifier}]}]
        if commentary is not None:
            items.append({"type": "message", "phase": "commentary", "content": [
                {"type": "output_text", "text": commentary}]})
        items.append({"type": "function_call", "name": "lookup", "call_id": identifier,
                      "arguments": {"q": query}})
        if batch:
            items.append({"type": "function_call", "name": "lookup", "call_id": identifier + "-2",
                          "arguments": {"q": "another"}})
        return LLMResult.from_response({"id": identifier, "output": items})

    monkeypatch.setattr(extension, "call_extensions_sync", lambda *args, **kwargs: None)
    agent = object.__new__(Agent)
    agent.agent_name = "A0"
    agent.data = {}
    agent.loop_data = LoopData()
    agent.history = history.History(agent)
    agent.parse_prompt = lambda name, **kwargs: kwargs["message"]
    agent.hist_add_message = agent.history.add_message
    agent._remember_llm_result_state = lambda *args: None
    agent.read_prompt = lambda *args, **kwargs: "repeat"
    agent.context = SimpleNamespace(log=SimpleNamespace(log=lambda **kwargs: None))
    previous = result(old_query, old_text, old_batch, "old")
    current = result(new_query, new_text, new_batch, "new")
    original = current.to_dict()
    message = agent.hist_add_ai_response(previous.response, llm_result=previous)
    data = {"llm_result": current}

    RepeatResponse(agent).execute(data)

    assert bool(data.get("skip_default_processing")) is repeated
    assert message.content == previous.function_calls_text()
    assert current.to_dict() == original
    assert result_from_metadata(current.metadata()).repeat_response_text() == current.repeat_response_text()
    messages = agent.history.all_messages()
    assert len(messages) == (3 if repeated else 1)
    if repeated:
        assert messages[1].content == current.function_calls_text()
        assert messages[1].metadata == current.metadata()


@pytest.mark.parametrize("field", ["thoughts", "headline"])
@pytest.mark.parametrize("change", ["same", "changed", "removed", "added"])
def test_chat_repeat_includes_public_planning_fields(field, change):
    previous = {"thoughts": ["Wait"], "headline": "Checking", "tool_name": "code_execution_tool",
                "tool_args": {"runtime": "output", "session": 0}}
    current = dict(previous)
    if change == "changed":
        current[field] = ["Still waiting"] if field == "thoughts" else "Checking again"
    elif change == "removed":
        current.pop(field)
    elif change == "added":
        previous.pop(field)
    agent = FakeAgent(json.dumps(current), last_response=json.dumps(previous))

    assert bool(_run(agent).get("skip_default_processing")) is (change == "same")


def test_truncated_result_warns_about_output_limit_instead_of_misformat():
    agent = FakeAgent('{"thoughts":["planning"],"tool_name":"response","tool_args":{"text":"cut')

    result = _run(agent, finish_reason="length", truncated=True, function_calls=[])

    assert result["skip_default_processing"] is True
    assert agent.history == []
    assert agent.warnings == ["output limit"]
    assert agent.logs == [
        {"type": "warning", "content": "truncated (length)", "id": "warning"}
    ]


def test_truncated_result_with_complete_tool_request_is_processed_normally():
    agent = FakeAgent('{"tool_name":"response","tool_args":{"text":"done"}}')

    result = _run(agent, finish_reason="length", truncated=True, function_calls=[])

    assert "skip_default_processing" not in result
    assert agent.warnings == []


@pytest.mark.parametrize("arguments,complete", [
    ('{"text":"done"}', True),
    ({"text": "done"}, True),
    ('{}', True),
    ('{"text":"cut', False),
    ('', False),
    ('[]', False),
    (None, False),
])
def test_truncated_native_call_requires_complete_arguments(arguments, complete):
    result = LLMResult.from_chat(
        response="", finish_reason="length", output_items=[
            {"type": "function_call", "name": "response", "call_id": "call_cut",
             "arguments": arguments},
        ],
    )
    agent = FakeAgent(result.response)
    data = {"llm_result": result}

    TruncatedResponse(agent).execute(data)

    assert bool(data.get("skip_default_processing")) is not complete
    assert agent.warnings == ([] if complete else ["output limit"])
    assert agent.history == []


def test_truncated_batch_retries_if_any_native_call_is_incomplete():
    result = LLMResult.from_chat(
        response="", finish_reason="length", output_items=[
            {"type": "function_call", "name": "response", "arguments": arguments}
            for arguments in ('{"text":"done"}', '{"text":"cut')
        ],
    )
    agent = FakeAgent(result.response)
    data = {"llm_result": result}

    TruncatedResponse(agent).execute(data)

    assert data["skip_default_processing"] is True
    assert agent.warnings == ["output limit"]
