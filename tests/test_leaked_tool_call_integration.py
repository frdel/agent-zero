from types import SimpleNamespace

import pytest

from agent import Agent, LoopData
from extensions.python.message_loop_result._05_leaked_tool_call import LeakedToolCall
from extensions.python.message_loop_result._20_empty_response import EmptyResponse
from extensions.python.message_loop_result._30_repeat_response import RepeatResponse
from extensions.python._functions.agent.Agent.hist_add_warning.end import (
    _90_stop_unusable_response_loop as response_loop,
)
from helpers import extension, mcp_handler, subagents
from extensions.python.message_loop_result import _05_leaked_tool_call as recovery
from helpers.errors import HandledException
from helpers.files import read_prompt_file
from helpers.llm_result import LLMResult, ResponseItem
from helpers.tool import Response
from plugins._context_doctor.extensions.python.message_loop_result._10_context_doctor import (
    ContextDoctor,
)


class FakeAgent:
    def __init__(self, name_map=None):
        self.loop_data = LoopData(iteration=0)
        self.agent_name = "A0"
        self.name_map = (
            {"response": "response", "x": "x"} if name_map is None else name_map
        )
        self.history = []
        self.warnings = []
        self.logs = []
        self.remembered = []
        self.context = SimpleNamespace(log=SimpleNamespace(log=self.log))

    def log(self, **kwargs):
        self.logs.append(kwargs)
        return SimpleNamespace(id="log", update=lambda **kwargs: None)

    def get_data(self, key):
        assert key == "responses_tool_name_map"
        return self.name_map

    def read_prompt(self, name, **kwargs):
        return read_prompt_file(
            name, ["plugins/_context_doctor/prompts", "prompts"], **kwargs
        )

    def hist_add_ai_response(self, response, **kwargs):
        self.history.append(response)
        message = SimpleNamespace(id="assistant")
        self._remember_llm_result_state(kwargs["llm_result"], message)
        return message

    def _remember_llm_result_state(self, result, message):
        self.remembered.append((result, message))

    def hist_add_warning(self, message):
        self.warnings.append(message)
        data = {"kwargs": {"message": message}, "exception": None}
        response_loop.StopUnusableResponseLoop(self).execute(data)
        if data["exception"] is not None:
            raise data["exception"]
        return SimpleNamespace(id="warning")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "build_responses_function_tools",
        lambda agent: ([], {"response": "response", "x": "x"}),
    )
    monkeypatch.setattr(
        response_loop, "get_settings", lambda: {"max_consecutive_unusable_responses": 3}
    )
    monkeypatch.setattr(
        "plugins._context_doctor.extensions.python.message_loop_result._10_context_doctor.get_plugin_config",
        lambda *args, **kwargs: {"suppress_xml": True},
    )


def run_hooks(agent, result, doctor=True):
    data = {"llm_result": result}
    LeakedToolCall(agent).execute(data)
    if doctor:
        ContextDoctor(agent).execute(data)
    EmptyResponse(agent).execute(data)
    RepeatResponse(agent).execute(data)
    return data


@pytest.mark.parametrize("mode", ["chat_completions", "responses"])
@pytest.mark.parametrize("doctor", [True, False])
@pytest.mark.asyncio
async def test_recovered_response_executes_through_normal_dispatch(
    monkeypatch, mode, doctor
):
    executed = []

    class ResponseTool:
        async def before_execution(self, **kwargs):
            pass

        async def execute(self, **kwargs):
            executed.append(kwargs)
            return Response(message=kwargs["text"], break_loop=True)

        async def after_execution(self, response):
            pass

    async def no_op(*args, **kwargs):
        pass

    monkeypatch.setattr(extension, "call_extensions_async", no_op)
    monkeypatch.setattr(
        mcp_handler.MCPConfig,
        "get_instance",
        lambda: SimpleNamespace(get_tool=lambda *args: None),
    )
    agent = object.__new__(Agent)
    agent.data = {
        "responses_tool_name_map": (
            {"response": "response"} if mode == "responses" else {}
        )
    }
    agent.loop_data = LoopData()
    agent.agent_name = "A0"
    agent.context = SimpleNamespace(log=SimpleNamespace(log=lambda **kwargs: None))
    agent.get_tool = lambda **kwargs: ResponseTool()
    agent.handle_intervention = no_op
    result = LLMResult(
        response='<tool_call>{"name":"response","arguments":{"text":"done"}}</tool_call>',
        mode=mode,
    )

    assert not run_hooks(agent, result, doctor).get("skip_default_processing")
    assert await Agent.process_llm_result_tools(agent, result) == "done"
    assert executed == [{"text": "done"}]
    assert agent.loop_data.current_tool is None


@pytest.mark.parametrize("doctor", [True, False])
@pytest.mark.parametrize("mode", ["chat_completions", "responses"])
@pytest.mark.parametrize(
    "text",
    [
        "<function=response><parameter=text>cut off",
        '{"tool_name":"response","tool_args":{"text":"cut off',
        '<tool_call>{"name":"unoffered","arguments":{}}</tool_call>',
        "<function=response><parameter=text>one</parameter></function>"
        "<function=response><parameter=text>two</parameter></function>",
        '{"tool_name":"response","tool_args":{"text":"one"}} '
        '{"tool_name":"response","tool_args":{"text":"two"}}',
    ],
)
def test_rejected_turn_skips_dispatch_and_stops_at_budget(doctor, mode, text):
    agent = FakeAgent()
    for iteration in range(3):
        agent.loop_data.iteration = iteration
        result = LLMResult(response=text, mode=mode)
        if iteration == 2:
            with pytest.raises(HandledException):
                run_hooks(agent, result, doctor)
        else:
            assert run_hooks(agent, result, doctor)["skip_default_processing"] is True
        assert result.response == text
        assert len(agent.history) == iteration + 1
        assert len(agent.warnings) == iteration + 1
        assert len(agent.remembered) == iteration + 1
    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 3


def test_missing_or_empty_surface_cannot_enable_recovery():
    for surface in ({}, None):
        agent = FakeAgent()
        agent.name_map = surface
        result = LLMResult(response='{"name":"response","arguments":{"text":"done"}}')
        assert run_hooks(agent, result)["skip_default_processing"] is True


def test_diagnostics_do_not_include_argument_contents():
    agent = FakeAgent()
    result = LLMResult(
        response='<tool_call>{"name":"x","arguments":{"secret":"fixture-secret"}}</tool_call>'
    )
    run_hooks(agent, result)
    assert "fixture-secret" not in str(
        agent.loop_data.params_temporary["leaked_tool_call"]
    )
    assert "fixture-secret" not in str(agent.logs)


@pytest.mark.parametrize(
    "item",
    [
        {
            "type": "function_call",
            "name": "x",
            "arguments": "{}",
            "call_id": "test-call",
        },
        {"type": "web_search_call", "id": "test-search"},
    ],
)
def test_native_transport_calls_are_not_recovered_twice(item):
    agent = FakeAgent()
    result = LLMResult(
        response="<function=x>", output_items=[ResponseItem.from_any(item)]
    )
    data = {"llm_result": result}
    LeakedToolCall(agent).execute(data)
    assert not data.get("skip_default_processing")
    assert not agent.history and not agent.warnings
    assert result.response == "<function=x>"


def test_discovered_recovery_hook_runs_before_context_doctor(monkeypatch):
    monkeypatch.setattr(extension.cache, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(extension.cache, "add", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        subagents,
        "get_paths",
        lambda *args: [
            "plugins/_context_doctor/extensions/python/message_loop_result",
            "extensions/python/message_loop_result",
        ],
    )
    names = [
        cls.__name__ for cls in extension._get_extension_classes("message_loop_result")
    ]
    assert (
        names.index("LeakedToolCall")
        < names.index("ContextDoctor")
        < names.index("EmptyResponse")
    )


def test_rejected_response_advances_real_history_state_once(monkeypatch):
    from helpers import history

    monkeypatch.setattr(extension, "call_extensions_sync", lambda *args, **kwargs: None)
    agent = object.__new__(Agent)
    agent.data = {"responses_tool_name_map": {"response": "response"}}
    agent.loop_data = LoopData()
    agent.agent_name = "A0"
    agent.history = history.History(agent)
    agent.parse_prompt = lambda template, **kwargs: kwargs["message"]
    agent.hist_add_message = agent.history.add_message
    agent.context = SimpleNamespace(log=SimpleNamespace(log=lambda **kwargs: None))
    agent.read_prompt = lambda name: read_prompt_file(name, ["prompts"])
    agent.hist_add_warning = lambda **kwargs: SimpleNamespace(id="warning")
    remembered = []

    def remember(result, message):
        remembered.append(result)
        Agent._remember_llm_result_state(agent, result, message)

    agent._remember_llm_result_state = remember
    result = LLMResult(
        response="<function=response><parameter=text>cut off",
        response_id="synthetic-rejected-turn",
        provider_model_key="test/model",
    )
    data = {"llm_result": result}
    LeakedToolCall(agent).execute(data)
    assert data["skip_default_processing"] is True
    assert remembered == [result]
    messages = agent.history.all_messages()
    assert len(messages) == 1
    state = agent.get_data(Agent.DATA_NAME_RESPONSES_STATE)
    assert state["response_id"] == "synthetic-rejected-turn"
    assert state["history_counter"] == messages[0].sequence


@pytest.mark.parametrize(
    "text",
    [
        "Plain answer.",
        '{"tool_name":"response","tool_args":{"text":"done"}}',
        "<function=response><parameter=text>cut off",
        "Example: `<function=response></function>`",
        "<function=response></function><function=response></function>",
    ],
)
def test_chat_only_resolves_surface_for_a_complete_candidate(monkeypatch, text):
    def unexpected_build(agent):
        pytest.fail(
            "Ordinary, quoted, truncated or ambiguous text must not build schemas"
        )

    monkeypatch.setattr(recovery, "build_responses_function_tools", unexpected_build)
    agent = FakeAgent(name_map={})
    LeakedToolCall(agent).execute({"llm_result": LLMResult.from_chat(response=text)})


@pytest.mark.parametrize("surface", [{}, None, {"native_response": "response"}])
def test_chat_uses_current_surface_instead_of_a_stale_native_map(monkeypatch, surface):
    calls = []
    monkeypatch.setattr(
        recovery,
        "build_responses_function_tools",
        lambda agent: calls.append(agent) or ([], surface),
    )
    agent = FakeAgent(name_map={"native_response": "unoffered"})
    result = LLMResult.from_chat(
        response='{"name":"native_response","arguments":{"text":"done"}}'
    )
    data = {"llm_result": result}
    LeakedToolCall(agent).execute(data)
    assert calls == [agent]
    if surface:
        assert not data.get("skip_default_processing")
        assert result.response == '{"tool_name":"response","tool_args":{"text":"done"}}'
    else:
        assert data["skip_default_processing"] is True


def test_surface_discovery_failure_retries_without_disclosing_exception(monkeypatch):
    def failed_build(agent):
        raise RuntimeError("fixture-sensitive-provider-details")

    monkeypatch.setattr(recovery, "build_responses_function_tools", failed_build)
    agent = FakeAgent(name_map={})
    result = LLMResult.from_chat(
        response='{"name":"response","arguments":{"text":"done"}}'
    )
    data = {"llm_result": result}
    LeakedToolCall(agent).execute(data)
    assert data["skip_default_processing"] is True
    assert (
        agent.loop_data.params_temporary["leaked_tool_call"]["detail"]
        == "tool_surface_unavailable"
    )
    assert "fixture-sensitive" not in str(agent.logs + agent.warnings)


@pytest.mark.parametrize("mode", ["chat_completions", "responses"])
@pytest.mark.asyncio
async def test_recovered_call_still_obeys_execution_time_tool_policy(monkeypatch, mode):
    from helpers import tool_policy
    from helpers.errors import RepairableException
    from plugins._tool_access.extensions.python.tool_execute_before._10_enforce_tool_policy import (
        EnforceToolPolicy,
    )

    async def run_policy(point, agent, **kwargs):
        if point == "tool_execute_before":
            await EnforceToolPolicy(agent).execute(**kwargs)

    async def no_op(*args, **kwargs):
        pass

    class BlockedTool:
        before_execution = no_op

        async def execute(self, **kwargs):
            pytest.fail("A recovered call bypassed the execution policy")

    monkeypatch.setattr(extension, "call_extensions_async", run_policy)
    monkeypatch.setattr(tool_policy.subagents, "get_paths", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        tool_policy,
        "get_policy",
        lambda agent: {
            "mode": "custom",
            "default": "block",
            "mcp_default": "block",
            "allowed": [],
            "blocked": [],
        },
    )
    monkeypatch.setattr(
        mcp_handler.MCPConfig,
        "get_instance",
        lambda: SimpleNamespace(get_tool=lambda *args: None),
    )
    agent = object.__new__(Agent)
    agent.data = {"responses_tool_name_map": {"x": "x"}}
    agent.config = SimpleNamespace(profile="restricted")
    agent.context = SimpleNamespace(log=SimpleNamespace(log=lambda **kwargs: None))
    agent.loop_data = LoopData()
    agent.get_tool = lambda **kwargs: BlockedTool()
    agent.handle_intervention = no_op
    result = LLMResult(response="<function=x></function>", mode=mode)
    LeakedToolCall(agent).execute({"llm_result": result})
    assert agent.loop_data.params_temporary["leaked_tool_call"]["status"] == "salvaged"
    with pytest.raises(RepairableException, match='Tool "x" is blocked'):
        await Agent.process_llm_result_tools(agent, result)
    assert agent.loop_data.current_tool is None
