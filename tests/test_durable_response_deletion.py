"""Delete known provider responses before their durable recovery data is scrubbed."""
import json
from pathlib import Path

import pytest

from agent import AgentConfig, AgentContext
from helpers import persist_chat
from helpers.durable import codec, runtime
from helpers.llm_result import LLMResult

from test_durable_runtime import rig


def known_model_outcome(rig, response_id="resp-known", context=None):
    context = context or rig.context
    run = rig.owner.sync("admit", context.id, "input", {}, codec.checkpoint(context.agent0))
    rig.owner.sync("start_call", run["run_id"], "model:0", "model", {})
    result = codec.result_payload(context.agent0, LLMResult(response_id=response_id))
    # Simulate a known body outcome saved before history and compatibility chat.
    rig.owner.sync("finish_call", run["run_id"], "model:0", result)
    return run


def test_new_chat_known_result_is_cleaned_after_fence_before_payload_scrub(rig, monkeypatch):
    run = known_model_outcome(rig)
    assert not persist_chat.chat_file_exists(rig.context.id)
    assert persist_chat._collect_response_ids(run["checkpoint"]["context"]) == []
    cleaned = []

    def provider_delete(response_ids):
        assert rig.owner.sync("get_run", run["run_id"])["status"] == "cancelled"
        assert rig.owner.sync("get_call", run["run_id"], "model:0")["result"]["response_id"] == "resp-known"
        assert not rig.owner.store._connection.in_transaction
        cleaned.append(response_ids)
        return []

    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", provider_delete)
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == [["resp-known"]]
    assert rig.owner.sync("get_call", run["run_id"], "model:0")["result"] is None


def test_owned_descendant_without_snapshot_is_cleaned_before_ledger_deletion(rig, monkeypatch):
    parent = known_model_outcome(rig, "resp-parent")
    child = AgentContext(AgentConfig(mcp_servers=""), id="response-child")
    child._durable_origin = {"kind": "child", "mode": "subordinate", "parent_run_id": parent["run_id"],
                             "parent_context_id": rig.context.id, "parent_agent_number": 0,
                             "parent_call_id": "tool:0:0", "index": 0}
    child_run = known_model_outcome(rig, "resp-child", child)
    cleaned = []
    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", lambda ids: cleaned.extend(ids) or [])
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == ["resp-parent", "resp-child"]
    assert AgentContext.get(child.id) is None
    assert rig.owner.sync("get_call", child_run["run_id"], "model:0")["result"] is None


@pytest.mark.parametrize("policy_location", ["agent", "context"])
def test_checkpoint_opt_out_prevents_provider_cleanup_without_live_context_or_snapshot(rig, monkeypatch, policy_location):
    target = rig.context.agent0.data if policy_location == "agent" else rig.context.data
    target["responses_delete_on_chat_delete"] = False
    run = known_model_outcome(rig)
    # The codec intentionally stores only its allowlisted context data. A saved
    # legacy context policy is handled separately below; agent policy is retained.
    if policy_location == "context":
        checkpoint = run["checkpoint"]
        checkpoint["context"]["data"]["responses_delete_on_chat_delete"] = False
        rig.owner.sync("transition", run["run_id"], "model_inflight", checkpoint=checkpoint)
    AgentContext.remove(rig.context.id)
    cleaned = []
    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", lambda ids: cleaned.append(ids) or [])
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == []
    assert rig.owner.sync("get_call", run["run_id"], "model:0")["result"] is None


def test_normalized_model_identity_only_and_snapshot_ids_are_deduplicated(rig, monkeypatch):
    run = known_model_outcome(rig)
    rig.owner.sync("start_call", run["run_id"], "ignored", "tool", {})
    rig.owner.sync("finish_call", run["run_id"], "ignored", {"mode": "responses", "response_id": "resp-tool"})
    rig.owner.sync("start_call", run["run_id"], "model:1", "model", {})
    rig.owner.sync("finish_call", run["run_id"], "model:1", {
        "mode": "responses", "response_id": "resp-other", "raw": {"response_id": "resp-raw"},
        "metadata": {"responses": {"response_id": "resp-metadata"}}})
    rig.owner.sync("start_call", run["run_id"], "model:2", "model", {})
    rig.owner.sync("finish_call", run["run_id"], "model:2", {"mode": "chat_completions", "response_id": "resp-chat"})
    path = Path(persist_chat._get_chat_file_path(rig.context.id))
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"data": {"responses_state": {"response_id": "resp-known"}}}))
    cleaned = []
    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", lambda ids: cleaned.extend(ids) or [])
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == ["resp-known", "resp-other"]


def test_provider_failures_are_reported_by_count_without_private_error_or_ids(rig, monkeypatch, capsys):
    known_model_outcome(rig, "resp-private")
    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", lambda ids: [(ids[0], "private-provider-error")])
    persist_chat.remove_chat(rig.context.id)
    output = capsys.readouterr().out
    assert "provider response cleanup failed for 1 stored responses" in output
    assert "resp-private" not in output and "private-provider-error" not in output


@pytest.mark.parametrize("opt_out", [False, True])
def test_legacy_snapshot_cleanup_contract_is_preserved(rig, monkeypatch, opt_out):
    monkeypatch.setattr(runtime, "_service", None)
    path = Path(persist_chat._get_chat_file_path(rig.context.id))
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"agents": [{"data": {"responses_delete_on_chat_delete": not opt_out,
        "responses_state": {"response_id": "resp-legacy", "response_ids": ["resp-legacy", "resp-older"]}}}]}))
    cleaned = []
    monkeypatch.setattr(persist_chat, "delete_stored_response_ids", lambda ids: cleaned.append(ids) or [])
    persist_chat.remove_chat(rig.context.id)
    assert cleaned == ([] if opt_out else [["resp-legacy", "resp-older"]])
    assert not path.exists()
