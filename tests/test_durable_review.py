"""Operator decisions, typed documents and body-conflict continuation."""
import asyncio
import json
import threading

import pytest
from flask import Flask

from agent import AgentContext
from api.durability import Durability
from helpers.durable import codec, documents, review, runtime
from helpers.durable.store import ConflictError
from helpers.tool import Response, Tool
from helpers.tool_execution import execute_tool
from test_durable_runtime import rig, admitted


def held(rig, phase="model_inflight"):
    run = admitted(rig, phase)
    return rig.owner.sync("transition", run["run_id"], "needs_attention", status="attention", payload={"reason": "unknown_outcome"})


def token(rig, run):
    return rig.owner.sync("get_review", run["run_id"])["version"]


def test_review_confirmation_is_evidence_and_stop_not_a_fabricated_result(rig):
    run = held(rig)
    rig.owner.sync("start_call", run["run_id"], "model:0", "model", {"unknown": True})
    version = token(rig, run)
    result = review.resolve(rig.owner, rig.context.id, run["run_id"], version,
                            "confirmed_completed", "Verified sentinel-secret externally", "decision-1", "model:0")
    assert result["decision"] == "confirmed_completed"
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "cancelled"
    assert rig.owner.sync("get_call", run["run_id"], "model:0")["status"] == "intent"
    evidence, = rig.owner.sync("list_resolutions", run["run_id"])
    assert "sentinel-secret" not in evidence["note"]
    assert review.resolve(rig.owner, rig.context.id, run["run_id"], version,
                          "confirmed_completed", "Verified sentinel-secret externally", "decision-1", "model:0") == result
    assert rig.requests == []


def test_late_result_invalidates_review_without_cancelling_the_run(rig):
    run = held(rig)
    rig.owner.sync("start_call", run["run_id"], "model:0", "model", {})
    version = token(rig, run)
    rig.owner.sync("finish_call", run["run_id"], "model:0", {"known": True})
    with pytest.raises(ConflictError):
        review.resolve(rig.owner, rig.context.id, run["run_id"], version, "stop", "", "stale-decision")
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "attention"


def test_stop_fences_a_corrupt_checkpoint_without_decoding_it(rig):
    run = held(rig)
    original = rig.owner.sync
    from helpers.durable.store import IntegrityError
    from unittest.mock import patch
    with patch.object(rig.owner, "sync", side_effect=lambda method, *args, **kwargs:
                      (_ for _ in ()).throw(IntegrityError("Corrupt checkpoint")) if method == "get_run" else original(method, *args, **kwargs)):
        review.resolve(rig.owner, rig.context.id, run["run_id"], token(rig, run), "stop", "", "stop-corrupt")
    assert rig.owner.sync("list_run_headers", context_id=rig.context.id)[0]["status"] == "cancelled"


def test_resume_uses_exact_checkpoint_not_an_earlier_safe_phase(rig):
    run = admitted(rig, "iteration_ready")
    rig.owner.sync("transition", run["run_id"], "processing_model", checkpoint=run["checkpoint"])
    rig.owner.sync("transition", run["run_id"], "needs_attention", status="attention")
    run = rig.owner.sync("get_run", run["run_id"])
    assert review.checkpoint_phase(rig.owner, run) == "processing_model"
    assert review.resume_phase(rig.owner, rig.context, run) is None
    with pytest.raises(review.ReviewError):
        review.resolve(rig.owner, rig.context.id, run["run_id"], token(rig, run), "resume", "", "unsafe-resume")
    assert rig.requests == []


def test_safe_resume_dispatches_once_and_repeated_request_is_idempotent(rig):
    run = held(rig, "iteration_ready")
    version = token(rig, run)
    receipt = review.resolve(rig.owner, rig.context.id, run["run_id"], version, "resume", "", "safe-resume")
    assert rig.context.task.result_sync(timeout=10) == "Done"
    assert review.resolve(rig.owner, rig.context.id, run["run_id"], version, "resume", "", "safe-resume") == receipt
    assert len(rig.requests) == 1


def test_repeated_resume_repairs_failed_dispatch_without_reauthorizing(rig, monkeypatch):
    run = held(rig, "iteration_ready")
    version = token(rig, run)
    original = review._dispatch
    monkeypatch.setattr(review, "_dispatch", lambda *args: (_ for _ in ()).throw(RuntimeError("dispatch unavailable")))
    with pytest.raises(RuntimeError):
        review.resolve(rig.owner, rig.context.id, run["run_id"], version, "resume", "", "dispatch-retry")
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "running"
    monkeypatch.setattr(review, "_dispatch", original)
    review.resolve(rig.owner, rig.context.id, run["run_id"], version, "resume", "", "dispatch-retry")
    assert rig.context.task.result_sync(timeout=10) == "Done"
    assert len(rig.requests) == 1
    assert len(rig.owner.sync("list_resolutions", run["run_id"])) == 1


def test_repeated_attempt_repairs_failed_dispatch_but_never_reuses_consumed_grant(rig, monkeypatch):
    from langchain_core.messages import HumanMessage
    run = admitted(rig, "iteration_ready")
    turn = runtime.Turn(rig.owner, rig.context.agent0, run)
    asyncio.run(turn.model_intent(rig.context.agent0.get_chat_model(), [HumanMessage(content="Saved input")], {}))
    rig.owner.sync("transition", run["run_id"], "needs_attention", status="attention")
    version = token(rig, run)
    original = review._dispatch
    monkeypatch.setattr(review, "_dispatch", lambda *args: (_ for _ in ()).throw(RuntimeError("dispatch unavailable")))
    with pytest.raises(RuntimeError):
        review.resolve(rig.owner, rig.context.id, run["run_id"], version, "new_attempt", "", "attempt-dispatch", "model:0")
    monkeypatch.setattr(review, "_dispatch", original)
    receipt = review.resolve(rig.owner, rig.context.id, run["run_id"], version, "new_attempt", "", "attempt-dispatch", "model:0")
    assert rig.context.task.result_sync(timeout=10) == "Done"
    assert review.resolve(rig.owner, rig.context.id, run["run_id"], version, "new_attempt", "", "attempt-dispatch", "model:0") == receipt
    assert len(rig.requests) == 1


def test_documents_are_typed_masked_and_newer_schemas_are_not_overwritten(rig):
    plan = {"title": "sentinel-secret", "items": [{"id": "one", "text": "Work", "done": False}]}
    assert documents.read(rig.owner, rig.context, "todo")["revision"] == 0
    documents.update(rig.owner, rig.context, "todo", plan, 0, "first-edit")
    # A lost response to the first app write must also be repeatable.
    documents.update(rig.owner, rig.context, "todo", plan, 0, "first-edit")
    assert documents.read(rig.owner, rig.context, "todo")["value"]["title"] == "[MASKED]"
    with pytest.raises(ValueError):
        documents.update(rig.owner, rig.context, "todo", {"title": "Plan", "items": ()}, 1, "tuple-edit")
    rig.owner.sync("write_document", rig.context.id, "todo", 2, plan, 1, "future-edit")
    with pytest.raises(ValueError, match="newer"):
        documents.update(rig.owner, rig.context, "todo", plan, 2, "old-client")


def test_document_migration_is_pure_and_requires_explicit_revision_update():
    schema = documents.DocumentKind("example", 2, lambda: {"count": 0},
                                    lambda value: None, lambda value, version: {"count": value["n"]})
    old = {"value": {"n": 3}, "schema_version": 1, "revision": 8}
    assert schema.decode(old) == ({"count": 3}, 8, True)
    assert old["value"] == {"n": 3}


def test_reset_between_document_read_and_write_fences_the_app_edit(rig, monkeypatch):
    from helpers.durable.store import StaleRunError
    documents.update(rig.owner, rig.context, "todo", {"title": "Before reset", "items": []}, 0, "initial-plan")
    original = rig.owner.sync
    def read_then_reset(method, *args, **kwargs):
        result = original(method, *args, **kwargs)
        if method == "read_document":
            original("control", rig.context.id, "reset")
        return result
    monkeypatch.setattr(rig.owner, "sync", read_then_reset)
    with pytest.raises(StaleRunError):
        documents.update(rig.owner, rig.context, "todo", {"title": "Stale edit", "items": []}, 1, "stale-plan")
    assert original("read_document", rig.context.id, "todo")["value"]["title"] == "Before reset"


def test_document_draft_is_discarded_on_body_failure(rig):
    run = admitted(rig, "tools")
    rig.context._durable_turn = turn = runtime.Turn(rig.owner, rig.context.agent0, run)
    turn.recovered = False

    class Failing(Tool):
        async def execute(self, **kwargs):
            await self.documents.stage("todo", {"title": "Never committed", "items": []}, expected_revision=0)
            raise RuntimeError("body failed")

    tool = Failing(rig.context.agent0, "failing", None, {}, "", rig.context.agent0.loop_data)
    with pytest.raises(RuntimeError, match="body failed"):
        asyncio.run(execute_tool(tool, {}))
    assert rig.owner.sync("read_document", rig.context.id, "todo") is None
    assert rig.owner.sync("get_call", run["run_id"], "tool:0:0")["status"] == "intent"


@pytest.mark.parametrize("decision", ["keep_current", "apply_proposed"])
def test_document_conflict_preserves_known_body_and_finishes_without_repeating_it(rig, decision, monkeypatch):
    run = admitted(rig, "tools")
    rig.context._durable_turn = turn = runtime.Turn(rig.owner, rig.context.agent0, run)
    turn.recovered = False
    hits = []

    class Effect(Tool):
        async def execute(self, **kwargs):
            hits.append("external effect")
            await self.documents.stage("todo", {"title": "Proposed", "items": []}, expected_revision=0)
            documents.update(rig.owner, rig.context, "todo", {"title": "Concurrent app edit", "items": []}, 0, "app-edit")
            return Response("External effect completed", False)

    agent = rig.context.agent0
    tool = Effect(agent, "effect", None, {}, "", agent.loop_data)
    with pytest.raises(runtime.RecoveryHeld, match="document_conflict"):
        asyncio.run(execute_tool(tool, {}))
    body = rig.owner.sync("get_call", run["run_id"], "tool:0:0")
    assert body["status"] == "completed" and hits == ["external effect"]
    assert rig.owner.sync("get_call", run["run_id"], "tool:0:0:final") is None
    conflict, = rig.owner.sync("list_document_conflicts", run["run_id"])
    rig.owner.sync("resolve_document_conflict", run["run_id"], conflict["conflict_id"], decision, 1,
                   token(rig, run), "resolve-edit")
    turn.tool_index = 0
    from helpers import tool_policy
    policy = tool_policy.ensure_tool_allowed
    monkeypatch.setattr(tool_policy, "ensure_tool_allowed", lambda *args: (_ for _ in ()).throw(ValueError("Access removed")))
    with pytest.raises(runtime.RecoveryHeld, match="tool_access_changed"):
        asyncio.run(execute_tool(tool, {}))
    assert hits == ["external effect"]
    monkeypatch.setattr(tool_policy, "ensure_tool_allowed", policy)
    turn.tool_index = 0
    result = asyncio.run(execute_tool(tool, {}))
    assert result.message == "External effect completed" and hits == ["external effect"]
    assert rig.owner.sync("get_call", run["run_id"], "tool:0:0:final")["status"] == "completed"
    document = documents.read(rig.owner, rig.context, "todo")
    assert document["value"]["title"] == ("Proposed" if decision == "apply_proposed" else "Concurrent app edit")


def test_restore_select_leaves_unknown_unselected_and_selected_unknown_held(rig, tmp_path):
    run = held(rig)
    destination = tmp_path / "restored" / "state.sqlite3"
    destination.parent.mkdir(mode=0o700)
    rig.owner.sync("backup", destination)
    restored = runtime.RecoveryService(destination.parent)
    try:
        state = restored.sync("get_restore_state")
        version = restored.sync("get_review", run["run_id"])["version"]
        assert not restored.sync("can_resume", run["run_id"])
        review.restore_select(restored, [run["run_id"]], {run["run_id"]: version}, state["epoch"], "select-one")
        assert restored.sync("can_resume", run["run_id"])
        assert restored.sync("get_run", run["run_id"])["status"] == "attention"
        assert restored.driving == set() and rig.requests == []
    finally:
        restored.close()


def test_restore_selection_requires_explicit_active_workflow_dependencies(rig):
    parent = held(rig)
    # Seed a separate context's journal, preserving explicit child ownership.
    child_data = dict(parent["checkpoint"], origin={"kind": "child", "parent_run_id": parent["run_id"],
                                                  "parent_context_id": rig.context.id})
    child = rig.owner.sync("admit", "child-context", "child-input", {}, child_data)
    state = rig.owner.sync("get_restore_state")
    version = token(rig, parent)
    # Force review to exercise closure even on an ordinary, already authorized root.
    original = rig.owner.sync
    from unittest.mock import patch
    with patch.object(rig.owner, "sync", side_effect=lambda method, *args, **kwargs:
                      False if method == "can_resume" else original(method, *args, **kwargs)):
        with pytest.raises(review.ReviewError) as failure:
            review.restore_select(rig.owner, [parent["run_id"]], {parent["run_id"]: version}, state["epoch"], "missing-child")
    assert failure.value.required_ids == [child["run_id"]]
    assert rig.owner.sync("get_review_request", parent["run_id"], "missing-child") is None


def test_unrelated_corrupt_run_does_not_block_healthy_selection(rig, monkeypatch):
    from helpers.durable.store import IntegrityError
    healthy = held(rig)
    corrupt = rig.owner.sync("admit", "unrelated-context", "unrelated-input", {}, healthy["checkpoint"])
    original = rig.owner.sync
    def read(method, *args, **kwargs):
        if method == "get_run" and args[0] == corrupt["run_id"]:
            raise IntegrityError("Corrupt unrelated payload")
        return original(method, *args, **kwargs)
    monkeypatch.setattr(rig.owner, "sync", read)
    review.restore_select(rig.owner, [healthy["run_id"]], {healthy["run_id"]: token(rig, healthy)},
                          rig.owner.sync("get_restore_state")["epoch"], "healthy-selection")
    assert rig.owner.sync("get_run", healthy["run_id"])["status"] == "attention"


def test_compacted_review_receipt_cannot_stop_a_newer_run(rig):
    run = admitted(rig, "iteration_ready")
    version = token(rig, run)
    receipt = review.resolve(rig.owner, rig.context.id, run["run_id"], version, "stop", "Evidence", "stop-old")
    rig.owner.sync("compact", retain_terminal=0, max_age_days=0)
    newer = rig.owner.sync("admit", rig.context.id, "new-input", {}, codec.checkpoint(rig.context.agent0))
    assert review.resolve(rig.owner, rig.context.id, run["run_id"], version, "stop", "Evidence", "stop-old") == receipt
    assert rig.owner.sync("get_run", newer["run_id"])["status"] == "running"


def test_review_stop_includes_background_children_from_an_earlier_turn(rig):
    old = admitted(rig, "iteration_ready")
    rig.owner.sync("transition", old["run_id"], "completed", status="completed")
    child_data = dict(old["checkpoint"], origin={"kind": "child", "parent_run_id": old["run_id"],
                                                "parent_context_id": rig.context.id})
    child = rig.owner.sync("admit", "background-context", "background-input", {}, child_data)
    new = rig.owner.sync("admit", rig.context.id, "next-input", {}, codec.checkpoint(rig.context.agent0))
    review.resolve(rig.owner, rig.context.id, new["run_id"], token(rig, new), "stop", "", "stop-family")
    assert rig.owner.sync("get_run", child["run_id"])["status"] == "cancelled"


def test_restore_invalidates_copied_resolution_receipts(rig, tmp_path):
    run = held(rig, "iteration_ready")
    version = token(rig, run)
    review.resolve(rig.owner, rig.context.id, run["run_id"], version, "stop", "", "source-decision")
    destination = tmp_path / "copy" / "state.sqlite3"
    destination.parent.mkdir(mode=0o700)
    rig.owner.sync("backup", destination)
    restored = runtime.RecoveryService(destination.parent)
    try:
        assert not restored.sync("get_review_request", run["run_id"], "source-decision")["epoch_valid"]
        with pytest.raises(ConflictError, match="epoch"):
            review.resolve(restored, rig.context.id, run["run_id"], version, "stop", "", "source-decision")
    finally:
        restored.close()


def test_status_does_not_create_contexts_or_expose_private_envelopes(rig):
    run = held(rig)
    rig.owner.sync("start_call", run["run_id"], "model:0", "model", {"api_key": "unregistered-secret"})
    before = len(AgentContext.all())
    data = review.status(rig.owner)
    assert len(AgentContext.all()) == before
    assert "unregistered-secret" not in json.dumps(data)
    assert "api_key" not in json.dumps(data)
    assert data["runs"][0]["actions"]["resume"] is False


def test_status_prioritizes_held_work_and_exposes_all_inventory_pages(rig):
    held_run = held(rig)
    for index in range(55):
        run = rig.owner.sync("admit", f"terminal-{index}", "input", {}, {})
        rig.owner.sync("transition", run["run_id"], "completed", status="completed")
    first = review.status(rig.owner)
    assert first["runs"][0]["run_id"] == held_run["run_id"]
    assert first["total"] == 56 and first["next_offset"] == 50
    second = review.status(rig.owner, offset=first["next_offset"])
    assert len(first["runs"]) == 50 and len(second["runs"]) == 6
    assert second["next_offset"] is None
    assert len({row["run_id"] for row in [*first["runs"], *second["runs"]]}) == 56


def test_api_preserves_security_defaults_and_context_scope(rig):
    assert Durability.requires_auth() and Durability.requires_csrf()
    assert Durability.get_methods() == ["POST"]
    run = held(rig)
    handler = Durability(Flask("durability-test"), threading.RLock())
    response = asyncio.run(handler.process({"action": "resolve", "context": "other-context",
        "run_id": run["run_id"], "version": token(rig, run), "decision": "stop", "request_id": "wrong-scope"}, None))
    assert response.status_code == 404
    assert rig.owner.sync("get_run", run["run_id"])["status"] == "attention"


def test_api_never_returns_arbitrary_plugin_exception_text(rig, monkeypatch):
    handler = Durability(Flask("durability-error-test"), threading.RLock())
    monkeypatch.setattr(documents, "read", lambda *args: (_ for _ in ()).throw(RuntimeError("private-provider-secret")))
    response = asyncio.run(handler.process({"action": "document_read", "context": rig.context.id, "kind": "todo"}, None))
    assert response.status_code == 503
    assert "private-provider-secret" not in response.get_data(as_text=True)
