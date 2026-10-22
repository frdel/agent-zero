"""Operator grants authorize one retained request, never an automatic retry loop."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from agent import Agent, LoopData
from helpers import extension
from helpers.durable import codec, replay, retry, runtime
from helpers.llm_result import LLMResult
from helpers.tool import Tool, Response
from helpers.tool_execution import execute_tool
from tools.durable_plan import DurablePlan
from tools.response import ResponseTool
from test_durable_runtime import rig, admitted


def turn_for(rig, phase="iteration_ready"):
    run = admitted(rig, phase)
    turn = runtime.Turn(rig.owner, rig.context.agent0, run)
    rig.context._durable_turn = turn
    return turn


def grant(rig, turn, call_id, phase):
    rig.owner.sync("transition", turn.run_id, "needs_attention", status="attention")
    version = rig.owner.sync("get_review", turn.run_id)["version"]
    return rig.owner.sync("prepare_retry", turn.run_id, call_id, version, "operator-request", phase, eligible=True,
                          note="Verified the target before this explicit new attempt")


@pytest.mark.asyncio
async def test_saved_model_retry_preserves_request_and_caching_without_preparation(rig, monkeypatch):
    turn = turn_for(rig)
    messages = [SystemMessage(content="Prepared system"), HumanMessage(content="Prepared user")]
    model = turn.agent.get_chat_model()
    call_id = await turn.model_intent(model, messages, {"a0_retry_attempts": 0, "responses_prompt_replacements": {}},
                                     explicit_caching=True, background=False, stream_response=True, stream_reasoning=True)
    original = rig.owner.sync("get_call", turn.run_id, call_id)
    assert original["payload"]["request_version"] == 2 and original["payload"]["retry_eligible"]
    prepared = grant(rig, turn, call_id, "model_retry")
    monkeypatch.setattr(turn.agent, "prepare_prompt", AsyncMock(side_effect=AssertionError("Must reuse prepared request")))
    turn = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    rig.context._durable_turn = turn
    await turn.model_retry()
    assert turn.phase == "model_result"
    assert len(rig.requests) == 1
    request = rig.requests[0]
    assert [item.content for item in request["messages"]] == ["Prepared system", "Prepared user"]
    assert request["explicit_caching"] is True and request["a0_retry_attempts"] == 0
    assert request["response_callback"] is not None and request["reasoning_callback"] is not None
    assert request["responses_prompt_replacements"] == {}
    assert rig.owner.sync("get_call", turn.run_id, call_id)["status"] == "intent"
    assert rig.owner.sync("get_call", turn.run_id, prepared["call_id"])["status"] == "completed"
    with pytest.raises(runtime.RecoveryHeld, match="fresh_operator_grant"):
        await turn.model_retry()
    assert len(rig.requests) == 1


@pytest.mark.asyncio
async def test_granted_model_retry_runs_through_normal_recorded_result_completion(rig):
    turn = turn_for(rig)
    call_id = await turn.model_intent(turn.agent.get_chat_model(), [HumanMessage(content="Exact saved input")], {"a0_retry_attempts": 0})
    grant(rig, turn, call_id, "model_retry")
    run = rig.owner.sync("get_run", turn.run_id)
    task = rig.owner.dispatch(rig.context, run)
    assert await asyncio.to_thread(task.result_sync, timeout=10) == "Done"
    assert rig.owner.sync("get_run", turn.run_id)["status"] == "completed"
    assert len(rig.requests) == 1


@pytest.mark.asyncio
async def test_consumed_model_alias_is_not_sent_again_after_interruption(rig):
    turn = turn_for(rig)
    call_id = await turn.model_intent(turn.agent.get_chat_model(), [HumanMessage(content="Saved")], {"a0_retry_attempts": 0})
    grant(rig, turn, call_id, "model_retry")
    rig.owner.sync("begin_retry", turn.run_id, call_id)
    restored = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    with pytest.raises(runtime.RecoveryHeld, match="fresh_operator_grant"):
        await restored.model_retry()
    assert rig.requests == []


@pytest.mark.parametrize("kwargs", [
    {"responses_builtin_tools": [{"type": "web_search_preview"}]},
    {"tools": [{"type": "function"}]},
    {"temperature": 0.1, "unknown_control": True},
    {"responses_local_input_items": [{"type": "web_search_call"}]},
])
def test_model_retry_rejects_hosted_tools_raw_tools_and_unknown_controls(rig, kwargs):
    payload = retry.describe_model(rig.context.agent0, rig.context.agent0.get_chat_model(),
                                   [HumanMessage(content="Saved")], kwargs,
                                   explicit_caching=True, background=False, stream_response=False, stream_reasoning=False)
    assert payload["retry_eligible"] is False


def test_model_retry_rejects_resolved_secrets_and_multimodal_inputs(rig):
    for content in ("sentinel-secret", [{"type": "text", "text": "A picture"}]):
        payload = retry.describe_model(rig.context.agent0, rig.context.agent0.get_chat_model(),
                                       [HumanMessage(content=content)], {}, explicit_caching=True,
                                       background=False, stream_response=False, stream_reasoning=False)
        assert payload["retry_eligible"] is False
        assert "sentinel-secret" not in json.dumps(payload)


async def tool_intent(rig, cls, args):
    turn = turn_for(rig, "tools")
    turn.recovered = False
    tool = cls(turn.agent, "response" if cls is ResponseTool else "durable_plan", None, args, "", turn.agent.loop_data)
    turn.agent.loop_data.current_tool = tool
    await turn.tool_begin(tool, args)
    await tool.before_execution(**args)
    await turn.effective_tool_args("tool:0:0", args)
    turn.agent.loop_data.current_tool = None
    return turn, tool


@pytest.mark.asyncio
async def test_tool_retry_uses_committed_arguments_skips_before_and_reuses_finalized_alias(rig, monkeypatch):
    args = {"text": "Recorded response"}
    turn, original = await tool_intent(rig, ResponseTool, args)
    prepared = grant(rig, turn, "tool:0:0", "tools")
    restored = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    rig.context._durable_turn = restored
    tool = ResponseTool(turn.agent, "response", None, args, "", turn.agent.loop_data)
    before = AsyncMock(side_effect=AssertionError("before_execution must not repeat"))
    monkeypatch.setattr(tool, "before_execution", before)
    response = await execute_tool(tool, args)
    assert response.message == "Recorded response" and response.break_loop
    assert before.await_count == 0
    assert rig.owner.sync("get_call", turn.run_id, prepared["call_id"] + ":args")["payload"] == args
    assert rig.owner.sync("get_call", turn.run_id, "tool:0:0")["status"] == "intent"
    restored.tool_index = 0
    monkeypatch.setattr(tool, "execute", AsyncMock(side_effect=AssertionError("Finalized alias must be reused")))
    assert (await execute_tool(tool, args)).message == "Recorded response"


@pytest.mark.asyncio
async def test_consumed_tool_alias_holds_even_when_original_body_was_safe(rig):
    turn, tool = await tool_intent(rig, ResponseTool, {"text": "Response"})
    grant(rig, turn, "tool:0:0", "tools")
    rig.owner.sync("begin_retry", turn.run_id, "tool:0:0")
    restored = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    with pytest.raises(runtime.RecoveryHeld, match="explicit_tool_attempt_outcome_unknown"):
        await restored.tool_begin(tool, {"text": "Response"})


@pytest.mark.asyncio
async def test_durable_plan_retry_commits_one_document_revision_under_alias(rig, monkeypatch):
    monkeypatch.setattr(replay, "AUDITED_TOOLS", replay.AUDITED_TOOLS | {(DurablePlan.__name__, codec.identity(DurablePlan)["source"])})
    value = {"title": "Retained plan", "items": [{"id": "item", "text": "One action", "done": False}]}
    args = {"action": "replace", "expected_revision": 0, "value": value}
    turn, tool = await tool_intent(rig, DurablePlan, args)
    call = rig.owner.sync("get_call", turn.run_id, "tool:0:0")
    recorded_args = rig.owner.sync("get_call", turn.run_id, "tool:0:0:args")
    assert retry.retry_eligibility(turn.agent, call, prepared=recorded_args)[0]
    grant(rig, turn, "tool:0:0", "tools")
    rig.context._durable_turn = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    response = await execute_tool(tool, args)
    assert json.loads(response.message)["revision"] == 1
    document = rig.owner.sync("read_document", rig.context.id, "todo")
    assert document["revision"] == 1 and document["value"] == value


def test_generic_effect_tool_has_no_explicit_retry_adapter(rig):
    class Effect(Tool):
        async def execute(self, **kwargs):
            return Response("Effect", False)
    call = {"kind": "tool", "status": "intent", "payload": {"tool": codec.identity(Effect)}}
    prepared = {"status": "completed", "payload": {}}
    assert retry.retry_eligibility(rig.context.agent0, call, prepared=prepared)[0] is False


@pytest.mark.asyncio
async def test_late_known_original_model_result_prevents_consuming_the_grant(rig):
    turn = turn_for(rig)
    call_id = await turn.model_intent(turn.agent.get_chat_model(), [HumanMessage(content="Saved")], {"a0_retry_attempts": 0})
    prepared = grant(rig, turn, call_id, "model_retry")
    rig.owner.sync("finish_call", turn.run_id, call_id, {"late_known_result": True})
    with pytest.raises(runtime.RecoveryHeld, match="descriptor_ineligible"):
        await turn.model_retry()
    assert rig.owner.sync("get_call", turn.run_id, prepared["call_id"]) is None
    assert rig.owner.sync("get_retry", turn.run_id, call_id)["state"] == "pending"
    assert rig.requests == []


def test_unknown_message_metadata_is_not_silently_dropped(rig):
    payload = retry.describe_model(rig.context.agent0, rig.context.agent0.get_chat_model(),
                                   [HumanMessage(content="Saved", additional_kwargs={"unknown": "value"})], {},
                                   explicit_caching=True, background=False, stream_response=False, stream_reasoning=False)
    assert payload["retry_eligible"] is False


@pytest.mark.asyncio
async def test_policy_change_blocks_tool_grant_consumption(rig, monkeypatch):
    turn, tool = await tool_intent(rig, ResponseTool, {"text": "Response"})
    prepared = grant(rig, turn, "tool:0:0", "tools")
    monkeypatch.setattr("helpers.tool_policy.ensure_tool_allowed", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Denied")))
    restored = runtime.Turn(rig.owner, turn.agent, rig.owner.sync("get_run", turn.run_id))
    with pytest.raises(runtime.RecoveryHeld, match="current_audit"):
        await restored.tool_begin(tool, {"text": "Response"})
    assert rig.owner.sync("get_call", turn.run_id, prepared["call_id"]) is None


def test_model_retry_rechecks_inherited_generation_options(rig, monkeypatch):
    model = rig.context.agent0.get_chat_model()
    payload = retry.describe_model(rig.context.agent0, model, [HumanMessage(content="Saved")], {},
                                   explicit_caching=True, background=False, stream_response=False, stream_reasoning=False)
    model.kwargs = {**model.kwargs, "temperature": 0.8}
    monkeypatch.setattr(rig.context.agent0, "get_chat_model", lambda: model)
    assert retry.model_eligibility(rig.context.agent0, payload)[0] is False
